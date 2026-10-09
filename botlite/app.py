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
from botlite.config import BOT_TOKEN, MAX_CONCURRENT_DOWNLOADS, WEBAPP_PUBLIC_URL
from botlite.utils.system import cleanup_old_temps, setup_signals

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
    setup_signals(client.disconnect)
    cleanup_old_temps()
    db.init()

    try:
        await client.start(bot_token=BOT_TOKEN)

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
            if WEBAPP_PUBLIC_URL:
                from botlite.webapp import stop_webapp
                await stop_webapp()
        finally:
            await client.disconnect()


def run() -> None:
    asyncio.run(_main())
