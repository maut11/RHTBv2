# channels/base_parser.py
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from openai import OpenAI

class BaseParser(ABC):
    """
    An abstract base class for channel message parsers.
    It handles the common logic of calling the OpenAI API, parsing JSON,
    and basic error handling, leaving channel-specific logic to subclasses.
    """
    def __init__(self, openai_client: OpenAI, channel_id: int, name: str):
        self.client = openai_client
        self.channel_id = channel_id
        self.name = name
        self._current_message_meta = None

    @abstractmethod
    def build_prompt(self) -> str:
        """
        Builds the channel-specific prompt for the OpenAI API.
        Must be implemented by each subclass.
        """
        pass

    def _call_openai(self, prompt: str) -> dict | list | None:
        """Makes the API call to OpenAI and parses the JSON response."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            content = response.choices[0].message.content.strip()
            if not content:
                print(f"❌ [{self.name}] Parsing failed: Empty response from OpenAI")
                return None
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"❌ [{self.name}] JSON parse error: {e}\nRaw content: {content}")
            return None
        except Exception as e:
            print(f"❌ [{self.name}] OpenAI API error: {e}")
            return None

    def parse_message(self, message_meta) -> list[dict]:
        """
        Main parsing method to be called by the bot.
        It orchestrates the prompt building, API call, and normalization.
        """
        self._current_message_meta = message_meta
        prompt = self.build_prompt()
        parsed_data = self._call_openai(prompt)
        if parsed_data is None:
            return []

        results = parsed_data if isinstance(parsed_data, list) else [parsed_data]
        
        normalized_results = []
        now = datetime.now(timezone.utc).isoformat()
        for entry in results:
            if not isinstance(entry, dict) or entry.get("action") == "null":
                continue
            
            # Add common metadata
            entry["channel_id"] = self.channel_id
            entry["received_ts"] = now
            
            # Allow subclasses to perform custom normalization
            entry = self._normalize_entry(entry)
            normalized_results.append(entry)

        return normalized_results

    def _normalize_entry(self, entry: dict) -> dict:
        """
        Optional hook for subclasses to perform custom normalization.
        By default, it does nothing.
        """
        return entry