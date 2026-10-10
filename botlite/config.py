"""
botlite.config
~~~~~~~~~~~~~~
Loads all configuration from environment variables / .env file.
"""

from __future__ import annotations

import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return default


def _int_list(key: str) -> list[int]:
    raw = os.getenv(key, "")
    values = []
    for item in raw.split(","):
        try:
            values.append(int(item.strip(), 10))
        except ValueError:
            continue
    return values


def _nonzero_int_list(key: str) -> set[int]:
    # Telegram supergroup/channel IDs are commonly negative.
    return {value for value in _int_list(key) if value != 0}


def _bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# ── Telegram ──────────────────────────────────────────────────────────────────
API_ID = _int("API_ID", 0)
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ── Admins ────────────────────────────────────────────────────────────────────
SUDO_USERS: list[int] = _int_list("SUDO_USERS") or []

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE = _int("MAX_FILE_SIZE", 2 * 1024 * 1024 * 1024)
MAX_CONCURRENT_DOWNLOADS = _int("MAX_CONCURRENT_DOWNLOADS", 3)
MIN_FREE_DISK = _int("MIN_FREE_DISK", 500 * 1024 * 1024)
USER_COOLDOWN = _int("USER_COOLDOWN", 5)
ALLOW_GROUPS = _bool("ALLOW_GROUPS", False)
ALLOWED_GROUP_IDS = _nonzero_int_list("ALLOWED_GROUP_IDS")
VOICE_ENABLED = _bool("VOICE_ENABLED", False)
VOICE_MAX_DURATION = _int("VOICE_MAX_DURATION", 1800)
VOICE_MAX_FILE_SIZE = _int("VOICE_MAX_FILE_SIZE", 100 * 1024 * 1024)

# ── Storage ───────────────────────────────────────────────────────────────────
DB_FILE = os.getenv("DB_FILE", "media_bot.db")

# ── WebApp dashboard (optional) ───────────────────────────────────────────────
# Set WEBAPP_PUBLIC_URL to enable the embedded web server and add dashboard
# buttons to bot replies.  The URL must be HTTPS for Telegram to open it as
# a WebApp (use a reverse proxy / Cloudflare Tunnel for self-hosted setups).
WEBAPP_PUBLIC_URL = os.getenv("WEBAPP_PUBLIC_URL", "")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "127.0.0.1")
WEBAPP_PORT = _int("WEBAPP_PORT", 8080)
WEBAPP_INIT_DATA_MAX_AGE = _int("WEBAPP_INIT_DATA_MAX_AGE", 3600)


def validate() -> None:
    """Abort with a clear message if required credentials are missing."""
    errors = []
    if not API_ID:
        errors.append("API_ID is not set")
    if not API_HASH:
        errors.append("API_HASH is not set")
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if WEBAPP_PUBLIC_URL and not WEBAPP_PUBLIC_URL.lower().startswith("https://"):
        errors.append("WEBAPP_PUBLIC_URL must use HTTPS")
    if ALLOW_GROUPS and not ALLOWED_GROUP_IDS:
        errors.append("ALLOW_GROUPS requires at least one non-zero ALLOWED_GROUP_IDS entry")
    if VOICE_ENABLED and (not ALLOW_GROUPS or not ALLOWED_GROUP_IDS):
        errors.append(
            "VOICE_ENABLED requires ALLOW_GROUPS and an explicit ALLOWED_GROUP_IDS allowlist"
        )
    if VOICE_MAX_DURATION <= 0:
        errors.append("VOICE_MAX_DURATION must be greater than zero")
    if VOICE_MAX_FILE_SIZE <= 0:
        errors.append("VOICE_MAX_FILE_SIZE must be greater than zero")
    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        print("Set these in a .env file or as environment variables.", file=sys.stderr)
        sys.exit(1)
