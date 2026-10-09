"""
botlite.app
~~~~~~~~~~~
Application bootstrap: wires all modules together and starts the bot.
"""

from __future__ import annotations

import asyncio
import logging
import sys

# Register all handlers (side-effect import)
import botlite.handlers  # noqa: F401
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("botlite.app")


async def _main() -> None:
    config.validate()

    async def disconnect() -> None:
        if VOICE_ENABLED:
            await get_voice_manager().shutdown()
        try:
            await client.disconnect()
        finally:
            if VOICE_ENABLED:
                get_voice_manager().cleanup_after_disconnect()

    setup_signals(disconnect)
    cleanup_old_temps()
    db.init()

    try:
        await client.start(bot_token=BOT_TOKEN)

        if VOICE_ENABLED:
            await initialize_voice().start()

        if WEBAPP_PUBLIC_URL:
            from botlite.webapp import start_webapp
            await start_webapp()

        log.info(
            "Bot Lite Downloader v%s started. Max concurrent: %d%s",
            VERSION,
            MAX_CONCURRENT_DOWNLOADS,
            f" | WebApp: {WEBAPP_PUBLIC_URL}" if WEBAPP_PUBLIC_URL else "",
        )
        await client.run_until_disconnected()
    finally:
        try:
            if VOICE_ENABLED:
                await get_voice_manager().shutdown()
            if WEBAPP_PUBLIC_URL:
                from botlite.webapp import stop_webapp
                await stop_webapp()
        finally:
            try:
                await client.disconnect()
            finally:
                if VOICE_ENABLED:
                    get_voice_manager().cleanup_after_disconnect()


def run() -> None:
    asyncio.run(_main())
