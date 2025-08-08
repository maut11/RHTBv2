# channels/will.py
from .base_parser import BaseParser

# --- Channel-specific Parser ---
CHANNEL_ID = 1257442835465244732

class WillParser(BaseParser):
    # The __init__ method now receives the config directly
    def __init__(self, openai_client, channel_id, config):
        # It no longer needs to look it up itself
        super().__init__(openai_client, channel_id, config["name"])


    def build_prompt(self) -> str:
        message_text = f"{self._current_message_meta[0]}\n{self._current_message_meta[1]}" if isinstance(self._current_message_meta, tuple) else self._current_message_meta
        return f"""
You are a trading assistant helping to extract structured swing trade data from Discord messages sent by a trader named Will.

Your job is to classify each message into one or more of the following categories:
- "buy": Entry into a new trade.
- "trim": Partial profit taken (e.g., sold a portion of contracts).
- "stop": Full exit from a position (e.g., closed all contracts).
- "null": Commentary, status updates, or non-actionable content.

Return a **list of JSON objects**, one per action. Each object must have the following fields:
- action: "buy", "trim", "stop", or "null"
- ticker: the stock symbol (e.g., JPM)
- strike: strike price (number), if present
- expiration: expiration in YYYY-MM-DD format, if present
- type: "call" or "put", if present
- price: contract price (number), if mentioned
- size: "full", "half", or "lotto" — based on context (e.g., "half size", "lotto", or tone)

Interpretation Rules:
- "Out", "Out of", "closing out", "going flat", or "done here" always imply a full exit ("stop"), even if followed by commentary.
- If the message includes "trim", "partial", or "took some", it's a "trim".
- "Position Update", "still holding", or mentions of account status without action = "null".
- Setting or updating stop-loss levels (e.g., "set SL", "stop now", "moving stop") = "null".
- Only label as "buy" if it contains "fill", "adding", "entry", or clearly initiates a new position.
- Sentiment, emojis, or casual remarks should not change the classification.
- If you're unsure, lean toward "null".
1. ENTRY: Represents a new trade. Must include Ticker, Strike, Option Type, and Entry Price.
2. TRIM: Represents a partial take-profit. Must include a price.
3. EXIT: Represents a full close of the position.
4. **Breakeven (BE): If the message indicates an exit at "BE" or "breakeven", you MUST return "BE" as the value for the "price" field. Example: {{"action": "exit", "price": "BE"}}**
5. COMMENT: Not a trade instruction. Return null.
Now classify this message. If it refers to multiple actions, return a list of JSON objects (one per action). If it is not actionable, return:

[
  {{
    "action": "null"
  }}
]

Return only valid JSON.

Message:
\"{message_text.strip()}\"
"""

    def _normalize_entry(self, entry: dict) -> dict:
        # Normalize ambiguous sizes
        if entry.get("size") in ("some", "small", "starter"):
            entry["size"] = "half"
        # Standardize exit action
        if entry.get("action") == "exit":
            entry["action"] = "stop"
        return entry