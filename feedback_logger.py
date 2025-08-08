# feedback_logger.py
import csv
import os
import json # <-- This line was missing
from threading import Lock

class FeedbackLogger:
    def __init__(self, filename="parsing_feedback.csv"):
        self.filename = filename
        self.lock = Lock()
        self._initialize_file()

    def _initialize_file(self):
        """Creates the CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.filename):
            with self.lock:
                # Double-check inside the lock
                if not os.path.exists(self.filename):
                    with open(self.filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            "Channel Name", 
                            "Original Message", 
                            "Parsed Message",
                            "Is_Correct (Y/N)",
                            "Notes"
                        ])

    def log(self, channel_name, original_message, parsed_message_json):
        """Appends a new row to the feedback CSV file in a thread-safe manner."""
        with self.lock:
            try:
                with open(self.filename, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        channel_name,
                        original_message,
                        json.dumps(parsed_message_json) # <-- This is where the error occurred
                    ])
            except Exception as e:
                print(f"❌ Failed to write to feedback log: {e}")

# Create a single, global instance to be used by the bot
feedback_logger = FeedbackLogger()