"""
botlite.webapp.server
~~~~~~~~~~~~~~~~~~~~~
aiohttp application: JSON API + static dashboard.

Endpoints
---------
GET  /                -> index.html (Telegram WebApp frontend)
GET  /api/status      -> public bot health (version, uptime, disk, downloads)
GET  /api/stats       -> sudo-only download counters
POST /api/ban         -> sudo-only; body: {"user_id": <int>}
POST /api/unban       -> sudo-only; body: {"user_id": <int>}

Authentication
--------------
All /api/stats, /api/ban, /api/unban require the caller to send the
Telegram WebApp initData in the ``X-Telegram-Init-Data`` header.
The user ID extracted from initData must be in SUDO_USERS.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from aiohttp import web

from botlite import VERSION, db
from botlite.client import active_downloads
from botlite.config import MAX_CONCURRENT_DOWNLOADS, SUDO_USERS
from botlite.utils.format import fmt_size, fmt_uptime
from botlite.utils.system import free_disk
from botlite.webapp.auth import validate_init_data

log = logging.getLogger("botlite.webapp")
_start_time = time.time()
_STATIC = Path(__file__).parent / "static"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_sudo(request: web.Request) -> dict:
    """
    Validate initData and check sudo membership.
    Raises HTTP 401 / 403 on failure; returns the user dict on success.
    """
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = validate_init_data(init_data)
    if user is None:
        raise web.HTTPUnauthorized(reason="Invalid initData")
    if user.get("id") not in SUDO_USERS:
        raise web.HTTPForbidden(reason="Not a sudo user")
    return user


def _require_user(request: web.Request) -> dict:
    """Validate fresh Telegram initData for any authenticated Mini App user."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = validate_init_data(init_data)
    if user is None or not user.get("id"):
        raise web.HTTPUnauthorized(reason="Invalid initData")
    return user


# ── API handlers ──────────────────────────────────────────────────────────────

async def api_status(_request: web.Request) -> web.Response:
    response = web.json_response({
        "version": VERSION,
        "uptime": fmt_uptime(time.time() - _start_time),
        "active_downloads": len(active_downloads),
        "max_concurrent": MAX_CONCURRENT_DOWNLOADS,
        "free_disk": fmt_size(free_disk()),
        "free_disk_bytes": free_disk(),
    })
    response.headers["Cache-Control"] = "no-store"
    return response


async def api_me(request: web.Request) -> web.Response:
    user = _require_user(request)
    return web.json_response({
        "id": user.get("id"),
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "is_sudo": user.get("id") in SUDO_USERS,
    })


async def api_stats(request: web.Request) -> web.Response:
    _require_sudo(request)
    return web.json_response({
        "total_downloads": db.get_stat("total_downloads"),
        "failed_downloads": db.get_stat("failed_downloads"),
    })


async def api_ban(request: web.Request) -> web.Response:
    user = _require_sudo(request)
    try:
        data = await request.json()
        uid = int(data["user_id"])
    except (ValueError, TypeError, KeyError, web.HTTPException):
        raise web.HTTPBadRequest(reason="user_id must be an integer") from None
    if uid <= 0:
        raise web.HTTPBadRequest(reason="user_id must be positive")
    db.ban(uid)
    log.info("WebApp: user %d banned by admin %d", uid, user.get("id"))
    return web.json_response({"ok": True})


async def api_unban(request: web.Request) -> web.Response:
    user = _require_sudo(request)
    try:
        data = await request.json()
        uid = int(data["user_id"])
    except (ValueError, TypeError, KeyError, web.HTTPException):
        raise web.HTTPBadRequest(reason="user_id must be an integer") from None
    if uid <= 0:
        raise web.HTTPBadRequest(reason="user_id must be positive")
    db.unban(uid)
    log.info("WebApp: user %d unbanned by admin %d", uid, user.get("id"))
    return web.json_response({"ok": True})


# ── Static ────────────────────────────────────────────────────────────────────

async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(_STATIC / "index.html")


async def security_headers(request: web.Request, response: web.StreamResponse) -> None:
    """Set headers on every response, including framework-generated errors."""
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' https://telegram.org; connect-src 'self'; style-src 'self' 'unsafe-inline'",
    })


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.on_response_prepare.append(security_headers)
    app.router.add_get("/", index)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/stats", api_stats)
    app.router.add_post("/api/ban", api_ban)
    app.router.add_post("/api/unban", api_unban)
    return app
