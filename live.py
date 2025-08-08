# live.py
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
import discord
import aiohttp
from openai import OpenAI

# --- Load Environment & Config ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_USER_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LIVE_PLAY_WEBHOOK = os.getenv("LIVE_PLAY_WEBHOOK")
TEST_LOGGING_WEBHOOK = os.getenv("TEST_LOGGING_WEBHOOK") # For test-mode channels
LIVE_LOGGING_WEBHOOK = os.getenv("LIVE_LOGGING_WEBHOOK") # For the bot's own logs
LIVE_COMMAND_CHANNEL_ID = int(os.getenv("LIVE_COMMAND_CHANNEL_ID"))

from config import *
from position_manager import PositionManager
from trader import RobinhoodTrader, SimulatedTrader
from channels.sean import SeanParser
from channels.will import WillParser
from channels.eva import EvaParser
from channels.ryan import RyanParser
from channels.fifi import FifiParser
from feedback_logger import feedback_logger

# --- Global State & Initializations ---
SIM_MODE = False # Global simulation switch, controllable by command
openai_client = OpenAI(api_key=OPENAI_API_KEY)
live_trader = RobinhoodTrader()
sim_trader = SimulatedTrader()
position_manager = PositionManager("tracked_contracts_live.json")

# Build handlers from the single, unified config
CHANNEL_HANDLERS = {
    channel_id: globals()[f"{config['name']}Parser"](openai_client, channel_id, config)
    for channel_id, config in CHANNELS_CONFIG.items()
}
print(f"✅ Bot is listening to channels: {list(CHANNEL_HANDLERS.keys())}")

# --- Helper function to clean AI output ---
def normalize_keys(data: dict) -> dict:
    if not isinstance(data, dict): return data
    cleaned_data = {k.lower().replace(' ', '_'): v for k, v in data.items()}
    if 'ticker' in cleaned_data and isinstance(cleaned_data['ticker'], str):
        cleaned_data['ticker'] = cleaned_data['ticker'].replace('$', '').upper()
    if 'option_type' in cleaned_data: cleaned_data['type'] = cleaned_data.pop('option_type')
    if 'entry_price' in cleaned_data: cleaned_data['price'] = cleaned_data.pop('entry_price')
    return cleaned_data

# --- BLOCKING Trade Logic (Designed to be run in a separate thread) ---
def _blocking_handle_trade(loop, handler, message_meta, raw_msg):
    def log_sync(msg):
        asyncio.run_coroutine_threadsafe(MyClient.log_and_print_helper(msg), loop)

    try:
        parsed_results = handler.parse_message(message_meta)
        if not parsed_results: return

        for raw_trade_obj in parsed_results:
            trade_obj = normalize_keys(raw_trade_obj)
            
            if trade_obj.get("action") != "null":
                feedback_logger.log(
                    channel_name=handler.name,
                    original_message=raw_msg,
                    parsed_message_json=trade_obj
                )

            action = trade_obj.get("action", "").lower()
            if not action or action == "null": continue

            channel_id = trade_obj["channel_id"]
            config = CHANNELS_CONFIG[channel_id]
            is_channel_live = config['mode'] == 'live'
            
            play_webhook = LIVE_PLAY_WEBHOOK if is_channel_live else TEST_LOGGING_WEBHOOK
            use_real_trader = is_channel_live and not SIM_MODE
            trader = live_trader if use_real_trader else sim_trader
            
            log_sync(f"🕠 Handling trade for {handler.name}: {trade_obj} (Channel Mode: {config['mode'].upper()}, Global Sim: {SIM_MODE})")
            
            active_position = position_manager.find_position(channel_id, trade_obj) or {}
            symbol = trade_obj.get("ticker") or active_position.get("symbol")
            strike = trade_obj.get("strike") or active_position.get("strike")
            expiration = trade_obj.get("expiration") or active_position.get("expiration")
            opt_type = trade_obj.get("type") or active_position.get("type")
            
            trade_obj.update({'ticker': symbol, 'strike': strike, 'expiration': expiration, 'type': opt_type})

            if not all([symbol, strike, expiration, opt_type]):
                log_sync(f"❌ Aborted: Missing critical contract info after fallback. Details: {trade_obj}")
                continue

            price_val = trade_obj.get("price")
            price = 'BE' if isinstance(price_val, str) and price_val.upper() == 'BE' else float(price_val or 0.0)
            size = trade_obj.get("size", "full")
            result_summary = "Action not executed."

            if action == "buy":
                try:
                    if not isinstance(price, (int, float)) or price <= 0:
                        result_summary = "❌ Aborted: Invalid price for a buy order."
                    else:
                        portfolio_value = trader.get_portfolio_value()
                        allocation = MAX_PCT_PORTFOLIO * POSITION_SIZE_MULTIPLIERS.get(size, 1.0) * config["multiplier"]
                        max_amount = min(allocation * portfolio_value, MAX_DOLLAR_AMOUNT)
                        padded_price = price * (1 + BUY_PRICE_PADDING)
                        contracts = max(MIN_TRADE_QUANTITY, int(max_amount / (padded_price * 100)))
                        stop_price = round(price * (1 - config["initial_stop_loss"]), 2)
                        trader.place_option_buy_order(symbol, strike, expiration, opt_type, contracts, padded_price)
                        trader.place_option_stop_loss_order(symbol, strike, expiration, opt_type, contracts, stop_price)
                        result_summary = f"Placed BUY: {contracts}x {symbol} {strike}{opt_type} @ {padded_price:.2f} with stop @ {stop_price}"
                        position_manager.add_position(channel_id, trade_obj)
                except Exception as e:
                    result_summary = f"❌ API Error on BUY: {e}"

            elif action in ("trim", "exit", "stop"):
                if not active_position:
                    result_summary = "❌ No tracked position found to act on."
                else:
                    try:
                        if price == 'BE':
                            price = active_position.get('purchase_price', 0.0)
                            if not isinstance(price, (int, float)) or price <= 0:
                                raise ValueError("Breakeven price is invalid or missing from memory.")
                        pos_on_broker = trader.find_open_option_position(symbol, strike, expiration, opt_type)
                        if not pos_on_broker or float(pos_on_broker.get('quantity', 0)) == 0:
                            result_summary = f"Position {symbol} not on broker. Clearing from memory."
                            position_manager.clear_position(channel_id, active_position['trade_id'])
                        else:
                            instrument_url = pos_on_broker.get('legs', [{}])[0].get('option')
                            for order in trader.get_open_orders_for_contract(instrument_url):
                                trader.cancel_option_order(order['id'])
                            log_sync(f"✅ Canceled open orders for {symbol}.")
                            qty = int(float(pos_on_broker['quantity']))
                            if action == "trim":
                                trim_qty = max(1, qty // 4)
                                remaining = qty - trim_qty
                                trader.place_option_market_sell_order(symbol, strike, expiration, opt_type, trim_qty)
                                market_data = trader.get_option_market_data(symbol, expiration, strike, opt_type)
                                latest_price = float(market_data[0][0]['mark_price'])
                                trailing_stop_price = round(latest_price * (1 - config["trailing_stop_loss_pct"]), 2)
                                breakeven_price = float(active_position.get("purchase_price", 0.0))
                                new_stop_price = max(breakeven_price, trailing_stop_price)
                                trader.place_option_stop_loss_order(symbol, strike, expiration, opt_type, remaining, new_stop_price)
                                result_summary = f"Trimmed {trim_qty}, placed new stop on {remaining} @ {new_stop_price:.2f}"
                            else: # Full Exit
                                trader.place_option_market_sell_order(symbol, strike, expiration, opt_type, qty)
                                position_manager.clear_position(channel_id, active_position['trade_id'])
                                result_summary = f"Exited {qty} contracts of {symbol}."
                    except Exception as e:
                        result_summary = f"❌ API Error on {action.upper()}: {e}"
            
            log_sync(f"Execution Summary: {result_summary}")
            
            title_tag = "[LIVE]" if use_real_trader else "[SIMULATED]"
            if not is_channel_live:
                title_tag = "[TEST-MODE]"

            alert = {"username": "TradeBot", "embeds": [{ "title": f"{title_tag} [{handler.name}] {action.upper()}", "fields": [{"name": "Original Message", "value": raw_msg[:1024]}, {"name": "Parsed Message", "value": f"```json\n{json.dumps(trade_obj, indent=2)}```"}, {"name": "Execution Summary", "value": f"```{result_summary}```"}], "timestamp": datetime.utcnow().isoformat()}]}
            asyncio.run_coroutine_threadsafe(MyClient.send_webhook_helper(play_webhook, alert), loop)

    except Exception as e:
        log_sync(f"❌ An unhandled error occurred in the trade processing thread: {e}")

# --- Discord Bot Class (The Main Async Thread) ---
class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        MyClient.static_logger_webhook = LIVE_LOGGING_WEBHOOK

    @staticmethod
    async def send_webhook_helper(url, payload):
        if not url: return
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status not in (200, 204):
                        print(f"⚠️ Webhook error {resp.status}: {await resp.text()}")
            except Exception as e:
                print(f"❌ Webhook exception: {e}")
    
    @staticmethod
    async def log_and_print_helper(msg):
        print(msg)
        await MyClient.send_webhook_helper(MyClient.static_logger_webhook, {"content": msg, "username": "UnifiedBot Logger"})

    async def get_positions_string(self) -> str:
        try:
            positions = await self.loop.run_in_executor(None, live_trader.get_open_option_positions)
            if not positions:
                return "No open option positions."
            holdings = [f"• {p['chain_symbol']} {p['expiration_date']} {p['strike_price']}{p['type'].upper()[0]} x{int(float(p['quantity']))}" for p in positions]
            return "\n".join(holdings)
        except Exception as e:
            return f"Error retrieving holdings: {e}"

    async def on_ready(self):
        await MyClient.log_and_print_helper(f"✅ Logged in as {self.user} (Unified Bot)")

    async def on_message(self, message):
        if message.author == self.user: return

        if message.channel.id == LIVE_COMMAND_CHANNEL_ID and message.content.startswith('!'):
            await self.handle_command(message)
            return

        if message.channel.id in CHANNEL_HANDLERS:
            handler = CHANNEL_HANDLERS[message.channel.id]
            content = message.content or ""
            embed_description = ""
            embed_title = ""
            if message.embeds:
                embed = message.embeds[0]
                embed_description = embed.description or ""
                embed_title = embed.title or ""
            
            if not content and not embed_description:
                return

            raw_msg = f"Title: {embed_title}\nDesc: {embed_description}" if embed_title else content
            message_meta = (embed_title, embed_description) if embed_title else content

            self.loop.run_in_executor(None, _blocking_handle_trade, self.loop, handler, message_meta, raw_msg)
            return

    async def handle_command(self, message: discord.Message):
        global SIM_MODE
        parts = message.content.lower().split()
        command = parts[0]
        
        if command == "!sim":
            if len(parts) > 1 and parts[1] in ["on", "true"]:
                SIM_MODE = True
                await message.channel.send("✅ **Global Simulation Mode is now ON.** All channels will be simulated.")
            elif len(parts) > 1 and parts[1] in ["off", "false"]:
                SIM_MODE = False
                await message.channel.send("🚨 **Global Simulation Mode is now OFF.** Bot will follow per-channel modes.")
            else:
                await message.channel.send("Usage: `!sim on` or `!sim off`")
        
        elif command == "!status":
            sim_status = "ON" if SIM_MODE else "OFF"
            live_channels = [cfg['name'] for cfg in CHANNELS_CONFIG.values() if cfg['mode'] == 'live']
            test_channels = [cfg['name'] for cfg in CHANNELS_CONFIG.values() if cfg['mode'] == 'test']
            status_msg = (
                f"**Bot Status: OPERATIONAL**\n"
                f"**Global Simulation Mode:** `{sim_status}`\n"
                f"**Live-Mode Channels:** `{'`, `'.join(live_channels) or 'None'}`\n"
                f"**Test-Mode Channels:** `{'`, `'.join(test_channels) or 'None'}`"
            )
            await message.channel.send(status_msg)
        
        elif command == "!positions":
            await message.channel.send("⏳ Fetching live account positions...")
            pos_string = await self.get_positions_string()
            await message.channel.send(f"**Current Positions:**\n```\n{pos_string}\n```")

        elif command == "!portfolio":
            await message.channel.send("⏳ Fetching live account portfolio value...")
            portfolio_value = await self.loop.run_in_executor(None, live_trader.get_portfolio_value)
            await message.channel.send(f"💰 **Total Portfolio Value:** ${portfolio_value:,.2f}")

        elif command == "!reconnect":
            await message.channel.send("⏳ Reconnecting to Robinhood...")
            await self.loop.run_in_executor(None, live_trader.reconnect)

        elif command == "!cancel_all":
            await message.channel.send("⏳ Canceling ALL open orders on the live account...")
            try:
                orders = await self.loop.run_in_executor(None, live_trader.get_all_open_option_orders)
                if not orders:
                    await message.channel.send("✅ No open orders to cancel.")
                    return
                for order in orders:
                    await self.loop.run_in_executor(None, live_trader.cancel_option_order, order['id'])
                await message.channel.send(f"✅ Canceled {len(orders)} open order(s).")
            except Exception as e:
                await message.channel.send(f"❌ Error canceling orders: {e}")

# --- Main Entrypoint ---
if __name__ == "__main__":
    discord_client = MyClient()
    discord_client.run(DISCORD_TOKEN)