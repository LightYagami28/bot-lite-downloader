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
    if _runner is not None:
        raise RuntimeError("The Telegram WebApp server is already running")

    runner = web.AppRunner(create_app(), access_log=None)
    try:
        await runner.setup()
        site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
        await site.start()
    except BaseException:
        await runner.cleanup()
        raise

    _runner = runner
    log.info("WebApp dashboard listening on %s:%d", WEBAPP_HOST, WEBAPP_PORT)


async def stop_webapp() -> None:
    global _runner
    if _runner:
        runner = _runner
        _runner = None
        await runner.cleanup()
        log.info("WebApp dashboard stopped")
