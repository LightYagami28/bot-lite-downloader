"""
botlite.app
~~~~~~~~~~~
Application bootstrap: wires all modules together and starts the bot.
"""

from __future__ import annotations

import logging
import sys

from botlite import VERSION
from botlite import config, db
from botlite.client import client
from botlite.config import BOT_TOKEN, MAX_CONCURRENT_DOWNLOADS
from botlite.utils.system import cleanup_old_temps, setup_signals

# Register all handlers (side-effect import)
import botlite.handlers  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("botlite.app")


def run() -> None:
    config.validate()
    setup_signals(client.disconnect)
    cleanup_old_temps()
    db.init()

    client.start(bot_token=BOT_TOKEN)
    log.info(
        "Bot Lite Downloader v%s started. Max concurrent: %d",
        VERSION, MAX_CONCURRENT_DOWNLOADS,
    )
    client.run_until_disconnected()
