import os
import sys
from pathlib import Path

# Ensure repo root is in sys.path when pytest is invoked directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure import-time Telethon client initialization has non-empty credentials.
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "testhash")
os.environ.setdefault("BOT_TOKEN", "testbottoken")
