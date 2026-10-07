"""
botlite.client
~~~~~~~~~~~~~~
Singleton Telethon client and shared runtime state.
"""

from __future__ import annotations

import asyncio

from telethon import TelegramClient

from botlite.config import API_HASH, API_ID, MAX_CONCURRENT_DOWNLOADS

# ── Telethon client (singleton) ───────────────────────────────────────────────
client = TelegramClient("bot_lite", API_ID, API_HASH)

# ── Runtime state ─────────────────────────────────────────────────────────────
download_semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
active_downloads: set[int] = set()        # user_ids with a download in progress
_user_cooldowns: dict[int, float] = {}    # user_id → timestamp of last request
