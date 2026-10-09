"""
botlite.handlers.commands
~~~~~~~~~~~~~~~~~~~~~~~~~
Telegram command handlers: /start /help /status /stats /ban /unban
"""

from __future__ import annotations

import os
import time

from telethon import events
from telethon.tl.custom import Button

from botlite import db
from botlite.client import active_downloads, client
from botlite.config import (
    ALLOW_GROUPS,
    ALLOWED_GROUP_IDS,
    DB_FILE,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_FILE_SIZE,
    SUDO_USERS,
    USER_COOLDOWN,
    WEBAPP_PUBLIC_URL,
)
from botlite.handlers.access import is_message_allowed
from botlite.utils.format import fmt_size, fmt_uptime
from botlite.utils.system import free_disk

_start_time = time.time()


def is_sudo(uid: int) -> bool:
    return uid in SUDO_USERS


def _group_allowed(event) -> bool:
    return is_message_allowed(
        is_private=event.is_private,
        is_group=event.is_group,
        chat_id=event.chat_id,
        sender_id=event.sender_id,
        allow_groups=ALLOW_GROUPS,
        allowed_group_ids=ALLOWED_GROUP_IDS,
    )


def _dashboard_button() -> list | None:
    """Return a one-row inline keyboard with the WebApp button, or None."""
    if not WEBAPP_PUBLIC_URL:
        return None
    return [[Button.web_app("📊 Open Dashboard", url=WEBAPP_PUBLIC_URL)]]


# ── /start ────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern="/start"))
async def cmd_start(event):
    if not _group_allowed(event):
        return
    await event.reply(
        "👋 **Bot Lite Downloader**\n\n"
        "Send me any media link and I'll download it for you.\n\n"
        "**Supported sites:** YouTube, Instagram, TikTok, Twitter/X, Reddit, "
        "Pinterest, Vimeo, SoundCloud, and [hundreds more]"
        "(https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).\n\n"
        "**Commands:** `/help` `/status`",
        parse_mode="md",
        link_preview=False,
        buttons=_dashboard_button(),
    )


# ── /help ─────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern="/help"))
async def cmd_help(event):
    if not _group_allowed(event):
        return
    cooldown_line = f"• Cooldown between requests: {USER_COOLDOWN}s\n" if USER_COOLDOWN else ""
    await event.reply(
        "**📖 Usage**\n\n"
        "Just send a link — no commands needed.\n\n"
        "**🍪 Cookies (optional)**\n"
        "Place a `cookiesSiteName.txt` file (Netscape format) next to `run.py` "
        "to access age-restricted or private content.\n"
        "Examples: `cookiesyoutube.txt`, `cookiesinstagram.txt`\n\n"
        "Export with the "
        "[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/"
        "get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension.\n\n"
        "**⚠️ Limits**\n"
        f"• Max file size: {fmt_size(MAX_FILE_SIZE)}\n"
        f"{cooldown_line}"
        "• Some sites actively block bots",
        parse_mode="md",
        link_preview=False,
        buttons=_dashboard_button(),
    )


# ── /status ───────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern="/status"))
async def cmd_status(event):
    if not _group_allowed(event):
        return
    from botlite import VERSION
    disk      = free_disk()
    disk_warn = " ⚠️" if disk < 500 * 1024 * 1024 * 2 else ""
    await event.reply(
        f"**🤖 Bot Lite Downloader v{VERSION}**\n\n"
        f"⏱ Uptime: `{fmt_uptime(time.time() - _start_time)}`\n"
        f"🔄 Active downloads: `{len(active_downloads)}`\n"
        f"💿 Free disk: `{fmt_size(disk)}`{disk_warn}",
        parse_mode="md",
        buttons=_dashboard_button(),
    )


# ── /stats ────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern="/stats"))
async def cmd_stats(event):
    if not event.is_private or not is_sudo(event.sender_id):
        return
    total  = db.get_stat("total_downloads")
    failed = db.get_stat("failed_downloads")
    db_sz  = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
    await event.reply(
        f"**📊 Stats**\n\n"
        f"✅ Succeeded: `{total}`\n"
        f"❌ Failed:    `{failed}`\n"
        f"💾 DB size:   `{fmt_size(db_sz)}`\n"
        f"⏱ Uptime:    `{fmt_uptime(time.time() - _start_time)}`\n"
        f"🔄 Active:    `{len(active_downloads)}/{MAX_CONCURRENT_DOWNLOADS}`\n"
        f"💿 Free disk: `{fmt_size(free_disk())}`",
        parse_mode="md",
        buttons=_dashboard_button(),
    )


# ── /ban ──────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"/ban( \d+)?"))
async def cmd_ban(event):
    if not event.is_private or not is_sudo(event.sender_id):
        return
    match = event.pattern_match.group(1)
    if not match:
        await event.reply("Usage: `/ban USER_ID`", parse_mode="md")
        return
    uid = int(match.strip())
    db.ban(uid)
    await event.reply(f"🚫 User `{uid}` banned.", parse_mode="md")


# ── /unban ────────────────────────────────────────────────────────────────────

@client.on(events.NewMessage(pattern=r"/unban( \d+)?"))
async def cmd_unban(event):
    if not event.is_private or not is_sudo(event.sender_id):
        return
    match = event.pattern_match.group(1)
    if not match:
        await event.reply("Usage: `/unban USER_ID`", parse_mode="md")
        return
    uid = int(match.strip())
    db.unban(uid)
    await event.reply(f"✅ User `{uid}` unbanned.", parse_mode="md")
