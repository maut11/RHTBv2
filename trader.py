# trader.py
import os
import robin_stocks.robinhood as r
from dotenv import load_dotenv

load_dotenv()
ROBINHOOD_USER = os.getenv("ROBINHOOD_USER")
ROBINHOOD_PASS = os.getenv("ROBINHOOD_PASS")

class RobinhoodTrader:
    def __init__(self):
        self.login()

    def login(self):
        try:
            r.login(ROBINHOOD_USER, ROBINHOOD_PASS, expiresIn=31536000, store_session=True)
            print("✅ Robinhood login successful.")
        except Exception as e:
            print(f"❌ Robinhood login failed: {e}")

    def reconnect(self):
        print("⚙️ Attempting to reconnect to Robinhood...")
        try:
            r.login(ROBINHOOD_USER, ROBINHOOD_PASS, expiresIn=31536000, store_session=True)
            print("✅ Reconnected to Robinhood successfully.")
        except Exception as e:
            print(f"❌ Failed to reconnect to Robinhood: {e}")

    def get_portfolio_value(self) -> float:
        try:
            profile = r.load_portfolio_profile()
            return float(profile.get('equity', 0.0))
        except Exception as e:
            print(f"❌ Error fetching portfolio value: {e}")
            return 0.0

    def get_open_option_positions(self):
        return r.get_open_option_positions()

    def get_all_open_option_orders(self):
        return r.get_all_open_option_orders()

    def cancel_option_order(self, order_id):
        return r.cancel_option_order(order_id)
        
    def find_open_option_position(self, symbol, strike, expiration, opt_type):
        try:
            open_positions = self.get_open_option_positions()
            for pos in open_positions:
                if (pos['chain_symbol'].upper() == str(symbol).upper() and
                        float(pos['strike_price']) == float(strike) and
                        pos['expiration_date'] == str(expiration) and
                        pos['type'].lower() == str(opt_type).lower()):
                    return pos
            return None
        except Exception as e:
            print(f"❌ Error fetching open positions: {e}")
            return None
            
    def get_open_orders_for_contract(self, instrument_url):
        try:
            orders = self.get_all_open_option_orders()
            return [o for o in orders if o.get('legs', [{}])[0].get('option') == instrument_url]
        except Exception as e:
            print(f"❌ Error fetching open orders for instrument {instrument_url}: {e}")
            return []
            
    def place_option_buy_order(self, symbol, strike, expiration, opt_type, quantity, limit_price):
        return r.order_buy_option_limit(
            positionEffect='open', creditOrDebit='debit', price=round(limit_price, 2),
            symbol=symbol, quantity=quantity, expirationDate=expiration,
            strike=strike, optionType=opt_type, timeInForce='gtc'
        )

    def place_option_stop_loss_order(self, symbol, strike, expiration, opt_type, quantity, stop_price):
        return r.order_sell_option_stop_loss(
            positionEffect='close', price=round(stop_price, 2), symbol=symbol,
            quantity=quantity, expirationDate=expiration, strike=strike,
            optionType=opt_type, timeInForce='gtc'
        )

    def place_option_market_sell_order(self, symbol, strike, expiration, opt_type, quantity):
        return r.order_sell_option_market(
            positionEffect='close', symbol=symbol, quantity=quantity,
            expirationDate=expiration, strike=strike, optionType=opt_type,
            timeInForce='gtc'
        )

    def get_option_market_data(self, symbol, expiration, strike, opt_type):
        return r.get_option_market_data(symbol, expiration, strike, opt_type)


class SimulatedTrader(RobinhoodTrader):
    def __init__(self):
        print("✅ Initialized SimulatedTrader.")
        self.simulated_positions = {} # Use a dictionary for unique positions

    def login(self):
        pass

    def reconnect(self):
        print("[SIMULATED] Reconnect called.")
    
    def get_portfolio_value(self) -> float:
        return 100000.0

    def find_open_option_position(self, symbol, strike, expiration, opt_type):
        print(f"[SIMULATED] Searching for position: {symbol} {strike}{opt_type}")
        # Use a consistent key to find the position
        pos_key = f"{str(symbol).upper()}_{str(float(strike))}_{str(expiration)}_{str(opt_type).lower()}"
        position = self.simulated_positions.get(pos_key)
        if position:
            print(f"[SIMULATED] Found position: {position}")
        else:
            print("[SIMULATED] No matching position found.")
        return position

    def get_open_orders_for_contract(self, instrument_url):
        print(f"[SIMULATED] Getting open orders for {instrument_url}")
        return []

    def place_option_buy_order(self, symbol, strike, expiration, opt_type, quantity, limit_price):
        summary = f"[SIMULATED] BUY {quantity}x {symbol} {expiration} {strike}{opt_type} @ {limit_price:.2f}"
        
        pos_key = f"{str(symbol).upper()}_{str(float(strike))}_{str(expiration)}_{str(opt_type).lower()}"
        
        if pos_key in self.simulated_positions:
            # Average down logic
            existing_pos = self.simulated_positions[pos_key]
            old_qty = float(existing_pos['quantity'])
            old_total_cost = old_qty * float(existing_pos['average_price'])
            new_qty = float(quantity)
            new_total_cost = new_qty * float(limit_price)
            
            total_qty = old_qty + new_qty
            total_cost = old_total_cost + new_total_cost
            
            existing_pos['quantity'] = str(total_qty)
            existing_pos['average_price'] = str(total_cost / total_qty)
            print(f"[SIMULATED] Averaged position. New state: {existing_pos}")
        else:
            # Add a new position
            new_pos = {
                "chain_symbol": str(symbol), "strike_price": str(float(strike)),
                "expiration_date": str(expiration), "type": str(opt_type).lower(),
                "quantity": str(float(quantity)), "average_price": str(float(limit_price)),
                "option_id": "simulated_id", "legs": [{"option": "simulated_url"}]
            }
            self.simulated_positions[pos_key] = new_pos
            print(f"[SIMULATED] Added to internal state: {new_pos}")
            
        return {"detail": summary}

    def place_option_stop_loss_order(self, symbol, strike, expiration, opt_type, quantity, stop_price):
        summary = f"[SIMULATED] STOP-LOSS for {quantity}x {symbol} @ {stop_price}"
        print(summary)
        return {"detail": summary}

    def place_option_market_sell_order(self, symbol, strike, expiration, opt_type, quantity):
        summary = f"[SIMULATED] SELL {quantity}x {symbol} at market"
        pos_key = f"{str(symbol).upper()}_{str(float(strike))}_{str(expiration)}_{str(opt_type).lower()}"
        
        if pos_key in self.simulated_positions:
            current_qty = float(self.simulated_positions[pos_key]['quantity'])
            new_qty = current_qty - float(quantity)
            if new_qty < 0.01:
                del self.simulated_positions[pos_key]
                print(f"[SIMULATED] Position for {symbol} {strike}{opt_type} removed from state.")
            else:
                self.simulated_positions[pos_key]['quantity'] = str(new_qty)
                print(f"[SIMULATED] Position quantity for {symbol} updated to {new_qty}.")
        
        return {"detail": summary}
        
    def get_option_market_data(self, symbol, expiration, strike, opt_type):
        pos = self.find_open_option_position(symbol, strike, expiration, opt_type)
        if pos and 'average_price' in pos:
            simulated_price = float(pos['average_price']) * 1.5 
            print(f"[SIMULATED] Getting market data for {symbol}, returning realistic price: {simulated_price}")
            return [[{'mark_price': str(simulated_price)}]]
        return [[{'mark_price': '1.50'}]]