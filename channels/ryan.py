# channels/ryan.py
from datetime import datetime, timezone
from .base_parser import BaseParser

# --- Channel-specific Parser ---
CHANNEL_ID = 1072559822366576780

class RyanParser(BaseParser):
    # The __init__ method now receives the config directly
    def __init__(self, openai_client, channel_id, config):
        # It no longer needs to look it up itself
        super().__init__(openai_client, channel_id, config["name"])

    def build_prompt(self) -> str:
        title, description = self._current_message_meta if isinstance(self._current_message_meta, tuple) else ("UNKNOWN", self._current_message_meta)

        return f"""
You are a highly accurate assistant for parsing structured option trading signals from Discord.

Messages come from a trader named Ryan and are embedded alerts with one of the following titles: ENTRY, TRIM, EXIT, or COMMENT.

You will receive:
- A **title** indicating the type of action
- A **description** containing the trade message

Return a valid JSON object only if the title is ENTRY, TRIM, or EXIT.
Return `null` if the message is COMMENT or not a trade instruction.
--- RULES ---
1. ENTRY: Represents a new trade. Must include Ticker, Strike, Option Type, and Entry Price.
2. TRIM: Represents a partial take-profit. Must include a price.
3. EXIT: Represents a full close of the position.
4. **Breakeven (BE): If the message indicates an exit at "BE" or "breakeven", you MUST return "BE" as the value for the "price" field. Example: {{"action": "exit", "price": "BE"}}**
5. COMMENT: Not a trade instruction. Return null.

Each message falls into one of these categories:
1. ENTRY
- Represents a new trade.
- Must include: Ticker, Strike price, Option type, and Entry price.
- Optional: Size, Averaging flag, Expiration (if not present, it's a 0DTE trade for today).

2. TRIM
- Represents a partial take-profit.
- Must include a price.

3. EXIT
- Represents a full close of the position.

4. COMMENT
- Commentary, not a trade instruction. Return null.

Return only the valid JSON object. Do not include explanations or markdown formatting.

Now parse the following:

Title: "{title.strip()}"  
Description: "{description.strip()}"
"""

    def _normalize_entry(self, entry: dict) -> dict:
        title, description = self._current_message_meta if isinstance(self._current_message_meta, tuple) else ("UNKNOWN", self._current_message_meta)
        title_upper = title.strip().upper()

        if title_upper == "ENTRY":
            entry["action"] = "buy"
        elif title_upper == "TRIM":
            entry["action"] = "trim"
        elif title_upper == "EXIT":
            entry["action"] = "exit"

        if "avg" in description.lower() or "average" in description.lower() or "adding" in description.lower():
            entry["averaging"] = True
            
        # --- 0DTE Logic for Ryan ---
        # If no expiration is found, assume it's for the current day.
        if not entry.get("expiration"):
            entry["expiration"] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            print(f"[{self.name}] No expiration found, defaulting to 0DTE: {entry['expiration']}")

        return entry