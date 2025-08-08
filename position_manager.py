# position_manager.py
import json
import os
from threading import Lock
import uuid

class PositionManager:
    """
    A thread-safe class to manage and persist the state of multiple open trades 
    across all channels. It can track several simultaneous positions per channel.
    """
    def __init__(self, track_file: str):
        self.track_file = track_file
        self._lock = Lock()
        # _positions now stores a dictionary where each channel ID maps to a LIST of trades.
        self._positions = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.track_file):
            with open(self.track_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save(self):
        with open(self.track_file, 'w') as f:
            json.dump(self._positions, f, indent=2)

    def add_position(self, channel_id: int, trade_data: dict):
        """
        Adds a new position to the list for a given channel.
        Generates a unique ID for the trade to track it.
        """
        channel_id_str = str(channel_id)
        trade_id = str(uuid.uuid4()) # Unique ID for this specific trade
        
        contract_info = {
            "trade_id": trade_id,
            "symbol": trade_data.get("ticker"),
            "strike": trade_data.get("strike"),
            "type": trade_data.get("type"),
            "expiration": trade_data.get("expiration"),
            "purchase_price": trade_data.get("price"),
            "size": trade_data.get("size", "full")
        }
        
        contract_info = {k: v for k, v in contract_info.items() if v is not None}

        with self._lock:
            if channel_id_str not in self._positions:
                self._positions[channel_id_str] = []
            self._positions[channel_id_str].append(contract_info)
            self._save()
        print(f"✅ PositionManager: Added position for channel {channel_id_str}: {contract_info}")
        return contract_info

    def find_position(self, channel_id: int, trade_data: dict):
        """
        Finds a specific position for a channel based on contract details.
        If no details are provided, returns the most recently added position (LIFO).
        """
        channel_id_str = str(channel_id)
        with self._lock:
            active_trades = self._positions.get(channel_id_str, [])
            if not active_trades:
                return None

            # If specific contract details are provided, search for it
            if trade_data.get("ticker"):
                for trade in reversed(active_trades): # Search newest first
                    if (trade["symbol"] == trade_data.get("ticker") and
                        trade["strike"] == trade_data.get("strike") and
                        trade["expiration"] == trade_data.get("expiration") and
                        trade["type"] == trade_data.get("type")):
                        return trade
            
            # If no details provided, return the last trade added
            return active_trades[-1]

    def clear_position(self, channel_id: int, trade_id: str):
        """
        Removes a specific position from the list for a channel using its unique trade_id.
        """
        channel_id_str = str(channel_id)
        with self._lock:
            if channel_id_str in self._positions:
                initial_count = len(self._positions[channel_id_str])
                self._positions[channel_id_str] = [
                    trade for trade in self._positions[channel_id_str] if trade.get("trade_id") != trade_id
                ]
                if len(self._positions[channel_id_str]) < initial_count:
                    self._save()
                    print(f"✅ PositionManager: Cleared position {trade_id} for channel {channel_id_str}")
                if not self._positions[channel_id_str]:
                    del self._positions[channel_id_str] # Clean up empty list
                    self._save()