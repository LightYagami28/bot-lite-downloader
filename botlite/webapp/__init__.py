"""
botlite.webapp
~~~~~~~~~~~~~~
Optional embedded web server for the Telegram WebApp dashboard.
Start it only when WEBAPP_PUBLIC_URL is configured.
"""

from __future__ import annotations

import logging

from aiohttp import web

from botlite.config import WEBAPP_HOST, WEBAPP_PORT
from botlite.webapp.server import create_app

log = logging.getLogger("botlite.webapp")
_runner: web.AppRunner | None = None


async def start_webapp() -> None:
    global _runner
    app = create_app()
    _runner = web.AppRunner(app, access_log=None)
    await _runner.setup()
    site = web.TCPSite(_runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    log.info("WebApp dashboard listening on %s:%d", WEBAPP_HOST, WEBAPP_PORT)


async def stop_webapp() -> None:
    if _runner:
        await _runner.cleanup()
        log.info("WebApp dashboard stopped")
