import os

# Ensure import-time Telethon client initialization has non-empty credentials.
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "testhash")
os.environ.setdefault("BOT_TOKEN", "testbottoken")
