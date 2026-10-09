"""
botlite.utils.system
~~~~~~~~~~~~~~~~~~~~
OS-level helpers: disk space, temp cleanup, signal handling.
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
import signal
import tempfile
import time
from collections.abc import Awaitable, Callable

from botlite.config import USER_COOLDOWN

log = logging.getLogger("botlite.system")


def free_disk(path: str = ".") -> int:
    """Return free disk space in bytes for the filesystem at *path*."""
    try:
        return shutil.disk_usage(path).free
    except OSError as exc:
        log.warning("Unable to determine free disk space for %s: %s", path, exc)
        return 0


def cleanup_old_temps() -> None:
    """Remove stale botlite_ temp dirs older than 1 hour left by crashes."""
    pattern = os.path.join(tempfile.gettempdir(), "botlite_*")
    for d in glob.glob(pattern):
        try:
            if os.path.isdir(d) and (time.time() - os.path.getmtime(d)) > 3600:
                shutil.rmtree(d, ignore_errors=True)
                log.info("Cleaned stale temp dir: %s", d)
        except OSError as exc:
            log.warning("Unable to clean stale temp dir %s: %s", d, exc)


def check_cooldown(user_cooldowns: dict[int, float], user_id: int) -> float:
    """Return remaining cooldown seconds (0.0 if ready)."""
    if USER_COOLDOWN <= 0:
        return 0.0
    last = user_cooldowns.get(user_id, 0.0)
    return max(0.0, USER_COOLDOWN - (time.time() - last))


def setup_signals(disconnect_fn: Callable[[], Awaitable[object]]) -> None:
    """Schedule and observe asynchronous cleanup on SIGTERM/SIGINT."""
    loop = asyncio.get_running_loop()
    shutdown_requested = False

    def _observe_disconnect(task: asyncio.Task[object]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            log.warning("Telegram client shutdown was cancelled")
        except Exception:
            log.exception("Telegram client shutdown failed")

    def _request_disconnect(signum: int) -> None:
        nonlocal shutdown_requested
        if shutdown_requested:
            return
        shutdown_requested = True
        log.info("Received signal %s, shutting down…", signum)
        loop.call_soon_threadsafe(
            lambda: loop.create_task(disconnect_fn()).add_done_callback(_observe_disconnect)
        )

    def _handler(signum, _frame):
        _request_disconnect(signum)

    for shutdown_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(shutdown_signal, _handler)
        except (OSError, ValueError) as exc:
            log.warning("Unable to register handler for signal %s: %s", shutdown_signal, exc)
