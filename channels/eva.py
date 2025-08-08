# channels/eva.py
from datetime import datetime, timezone
from .base_parser import BaseParser

# --- Channel-specific Parser ---
CHANNEL_ID = 1072556084662902846

class EvaParser(BaseParser):
    # The __init__ method now receives the config directly
    def __init__(self, openai_client, channel_id, config):
        # It no longer needs to look it up itself
        super().__init__(openai_client, channel_id, config["name"])

    def build_prompt(self) -> str:
        title, description = self._current_message_meta if isinstance(self._current_message_meta, tuple) else ("UNKNOWN", self._current_message_meta)
  
        return f"""
You are a highly accurate assistant for parsing option trading messages from a trader named Eva. Each message is an embedded Discord alert with a title and description.

Eva uses three message types:
- **OPEN**: opening a new trade.
- **CLOSE**: closing a trade — could be a partial close (trim) or full close (stop).
- **UPDATE**: not a trading instruction. Ignore and return {{ "action": "null" }}.

You must:
1. Return structured JSON representing the trading action if it's an "OPEN" or "CLOSE".
2. For "UPDATE", return {{ "action": "null" }}.
3. If the message is "CLOSE", classify it as:
   - "trim" → if the message suggests a **partial take profit**.
   - "stop" → if the message suggests a **full exit**.
4. If you are unsure between trim and stop, default to "stop".
5. Extract these fields from the description: ticker, strike, type, price, size.
6. **Expiration**: If the expiration date is not mentioned, it is a 0DTE trade for today.

--- RULES ---
1. ENTRY: Represents a new trade. Must include Ticker, Strike, Option Type, and Entry Price.
2. TRIM: Represents a partial take-profit. Must include a price.
3. EXIT: Represents a full close of the position.
4. **Breakeven (BE): If the message indicates an exit at "BE" or "breakeven", you MUST return "BE" as the value for the "price" field. Example: {{"action": "exit", "price": "BE"}}**
5. COMMENT: Not a trade instruction. Return null.

Return **only** a JSON object.

Now classify the following embedded message:

Title: {title.strip()}
Description: {description.strip()}
"""

    def _normalize_entry(self, entry: dict) -> dict:
        title, _ = self._current_message_meta if isinstance(self._current_message_meta, tuple) else ("UNKNOWN", "")
        title_upper = title.strip().upper()

        # --- FIX: Normalize OPEN/CLOSE actions ---
        if title_upper == "OPEN":
            entry["action"] = "buy"
        elif title_upper == "CLOSE":
            # The prompt now directly asks for the action to be trim/stop,
            # but this handles cases where it might return a classification instead.
            entry["action"] = entry.get("classification", "stop")
        # --- END FIX ---

        if entry.get("action") == "buy":
            entry.setdefault("size", "full")
            if not entry.get("expiration"):
                entry["expiration"] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                print(f"[{self.name}] No expiration found, defaulting to 0DTE: {entry['expiration']}")

        return entry
