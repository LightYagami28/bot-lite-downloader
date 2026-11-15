"""Application bootstrap: wire all modules together and start the bot."""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys

from botlite import VERSION, config, db
from botlite.client import client
from botlite.config import (
    BOT_TOKEN,
    MAX_CONCURRENT_DOWNLOADS,
    VOICE_ENABLED,
    WEBAPP_PUBLIC_URL,
)
from botlite.utils.system import cleanup_old_temps, setup_signals
from botlite.voice import get_voice_manager, initialize_voice

# Register all handlers (side-effect import)
importlib.import_module("botlite.handlers")


def setup_logging() -> None:
    """Configure root logging to bot.log and stdout, unless already configured."""
    if not logging.root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler("bot.log", encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )


log = logging.getLogger("botlite.app")


async def _disconnect() -> None:
    if VOICE_ENABLED:
        await get_voice_manager().shutdown()
    try:
        await client.disconnect()
    finally:
        if VOICE_ENABLED:
            get_voice_manager().cleanup_after_disconnect()


async def _start_services() -> None:
    await client.start(bot_token=BOT_TOKEN)
    if VOICE_ENABLED:
        await initialize_voice().start()
    if WEBAPP_PUBLIC_URL:
        await importlib.import_module("botlite.webapp").start_webapp()


async def _stop_services() -> None:
    try:
        if VOICE_ENABLED:
            await get_voice_manager().shutdown()
        if WEBAPP_PUBLIC_URL:
            await importlib.import_module("botlite.webapp").stop_webapp()
    finally:
        try:
            await client.disconnect()
        finally:
            if VOICE_ENABLED:
                get_voice_manager().cleanup_after_disconnect()


async def _main() -> None:
    setup_logging()
    config.validate()
    setup_signals(_disconnect)
    cleanup_old_temps()
    db.init()

    try:
        await _start_services()
        log.info(
            "Bot Lite Downloader v%s started. Max concurrent: %d%s",
            VERSION,
            MAX_CONCURRENT_DOWNLOADS,
            f" | WebApp: {WEBAPP_PUBLIC_URL}" if WEBAPP_PUBLIC_URL else "",
        )
        await client.run_until_disconnected()
    finally:
        await _stop_services()


def run() -> None:
    """Run the bot until it disconnects."""
    asyncio.run(_main())
