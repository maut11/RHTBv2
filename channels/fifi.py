# channels/fifi.py
from .base_parser import BaseParser

class FiFiParser(BaseParser):
    def __init__(self, openai_client, channel_id, config):
        super().__init__(openai_client, channel_id, config["name"])

    def build_prompt(self) -> str:
        message_text = self._current_message_meta[0] if isinstance(self._current_message_meta, tuple) else self._current_message_meta
        # Customize this prompt based on your analysis of FiFi's messages
        return f"""
You are a highly strict data extraction assistant for a trader named FiFi. Your job is to find explicit trading commands and convert them to a JSON object. You must ignore all other commentary.

A message is ONLY a trading command if it contains a clear action word and a specific contract.

--- RULES ---
1.  **Strictly Identify Commands:** If the message is commentary or an opinion, you MUST return `{{"action": "null"}}`.
2.  **Extract Details:** If it is an explicit command, extract `ticker`, `strike`, `type`, `price`, `expiration`, and `size`.
3.  **Action Words:**
    * "BTO", "buy", "long" -> "buy"
    * "Trim", "scale out" -> "trim"
    * "STC", "sell", "exit", "close", "out" -> "exit"
4.  **DO NOT GUESS:** If any field is missing, omit the key from the JSON.
5.  **BREAKEVEN (BE):** If the message mentions exiting at "BE", return "BE" as the value for the "price" field.

Return only a valid JSON object.

--- MESSAGE ---
"{message_text.strip()}"
"""
