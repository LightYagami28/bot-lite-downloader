# config.py — Configure via .env file or environment variables (recommended for self-hosting).
# Fallback: edit the defaults below directly.
# ─────────────────────────────────────────────────────────────────────────────

import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional; use env vars or edit values below


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return default


def _int_list(key: str) -> list[int]:
    raw = os.getenv(key, "")
    return [int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]


# ── Telegram API credentials ──────────────────────────────────────────────────
# Create your app at https://my.telegram.org → API development tools
API_ID   = _int("API_ID",   0)
API_HASH = os.getenv("API_HASH", "")

# Get your bot token from @BotFather on Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN", "")


# ── Admin user IDs ────────────────────────────────────────────────────────────
# Comma-separated list in env: SUDO_USERS=123456,789012
# Or override here: SUDO_USERS = [123456789]
SUDO_USERS: list[int] = _int_list("SUDO_USERS") or []


# ── Download limits ───────────────────────────────────────────────────────────
MAX_FILE_SIZE            = _int("MAX_FILE_SIZE",            2 * 1024 * 1024 * 1024)  # 2 GB
MAX_CONCURRENT_DOWNLOADS = _int("MAX_CONCURRENT_DOWNLOADS", 3)

# Minimum free disk space required before accepting a download (bytes)
MIN_FREE_DISK            = _int("MIN_FREE_DISK",            500 * 1024 * 1024)       # 500 MB

# Seconds a user must wait between download requests (0 = disabled)
USER_COOLDOWN            = _int("USER_COOLDOWN",            5)


# ── Database ──────────────────────────────────────────────────────────────────
DB_FILE = os.getenv("DB_FILE", "media_bot.db")
