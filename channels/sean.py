# channels/sean.py
from .base_parser import BaseParser

# --- Channel-specific Parser ---
CHANNEL_ID = 1072555808832888945

class SeanParser(BaseParser):
    # The __init__ method now receives the config directly
    def __init__(self, openai_client, channel_id, config):
        # It no longer needs to look it up itself
        super().__init__(openai_client, channel_id, config["name"])

    def build_prompt(self) -> str:
        message_text = f"{self._current_message_meta[0]}\n{self._current_message_meta[1]}" if isinstance(self._current_message_meta, tuple) else self._current_message_meta
        return f"""
You are an expert trading assistant. Your job is to classify trader messages into one of the following four categories:

- "buy": The message indicates initiating a new position.
- "trim": The message suggests partially taking profit.
- "stop": The message implies selling fully due to risk or loss.
- "null": The message is not a trade instruction (e.g., commentary, sentiment, opinion, or general update).

Return a JSON object with:
- action: "buy", "trim", "stop", or "null"
- ticker: the stock symbol (e.g., TSLA)
- strike: strike price (number), if present
- expiration: expiration date in YYYY-MM-DD format, if present
- type: "call" or "put", if present
- price: contract price (number), if mentioned (e.g., 1.77)
- size: one of "full", "half", or "lotto" based on the language in the message

Size Notes:
- If the message contains "half size", or there is sentiment that it is moderately risky → size = "half"
- If the message contains "lotto", "very small size", or "very risky" → size = "lotto"
- If size is not mentioned → size = "full"

Messages without an explicit trade directive (e.g. “all cash”, “still holding”, “watching”, “flow on”, “considering”) must be labeled as: "action": "null"

Rules:
- If multiple tickers, return one object per ticker (only for exit/stop)
- If info is missing, return as much as can be confidently extracted
- Avoid inferring trades from general commentary or opinions
1. ENTRY: Represents a new trade. Must include Ticker, Strike, Option Type, and Entry Price.
2. TRIM: Represents a partial take-profit. Must include a price.
3. EXIT: Represents a full close of the position.
4. **Breakeven (BE): If the message indicates an exit at "BE" or "breakeven", you MUST return "BE" as the value for the "price" field. Example: {{"action": "exit", "price": "BE"}}**
5. COMMENT: Not a trade instruction. Return null.

Now classify this message:
\"\"\"{message_text}\"\"\"
"""