"""
botlite.handlers.commands
~~~~~~~~~~~~~~~~~~~~~~~~~
Telegram command handlers: /start /help /status /stats /ban /unban
"""

from __future__ import annotations

import html
import logging
import os
import re
import tempfile
import time

from telethon import events
from telethon.tl.custom import Button

from botlite import db
from botlite.client import _user_cooldowns, active_downloads, client, download_semaphore
from botlite.config import (
    ALLOW_GROUPS,
    ALLOWED_GROUP_IDS,
    DB_FILE,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_FILE_SIZE,
    SUDO_USERS,
    USER_COOLDOWN,
    VOICE_ENABLED,
    VOICE_MAX_DURATION,
    VOICE_MAX_FILE_SIZE,
    WEBAPP_PUBLIC_URL,
)
from botlite.downloader.ytdlp import download_audio
from botlite.handlers.access import is_message_allowed
from botlite.utils.format import fmt_size, fmt_uptime
from botlite.utils.system import check_cooldown, free_disk
from botlite.voice import get_voice_manager

_start_time = time.time()
_VOICE_URL_RE = re.compile(r"^/play(?:@\w+)?\s+(https?://\S+)\s*$", re.IGNORECASE)
log = logging.getLogger("botlite.commands")


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
    try:
        from telethon.tl import types

        return [
            [
                types.KeyboardInlineButton(
                    "📊 Open Dashboard", types.InlineButtonTypeWebView(WEBAPP_PUBLIC_URL)
                )
            ]
        ]
    except (AttributeError, TypeError):
        return [[Button.url("📊 Open Dashboard", url=WEBAPP_PUBLIC_URL)]]


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
    voice_line = (
        "• In allowlisted groups: `/play URL`, `/pause`, `/resume`, `/voice_stop`\n"
        if VOICE_ENABLED and event.is_group
        else ""
    )
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
        f"{voice_line}"
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

    disk = free_disk()
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
    total = db.get_stat("total_downloads")
    failed = db.get_stat("failed_downloads")
    db_sz = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
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


@client.on(events.NewMessage(pattern=r"^/play(?:@\w+)?(?:\s|$)"))
async def cmd_voice_play(event):
    if not VOICE_ENABLED or not event.is_group or not _group_allowed(event):
        return
    match = _VOICE_URL_RE.fullmatch((event.raw_text or "").strip())
    if match is None:
        await event.reply("Usage: `/play https://…`", parse_mode="md")
        return

    user_id = event.sender_id
    if db.is_banned(user_id):
        await event.reply("🚫 You are banned from using this bot.")
        return
    if user_id in active_downloads:
        await event.reply("⏳ Your previous download is still running. Please wait.")
        return
    wait = check_cooldown(_user_cooldowns, user_id)
    if wait > 0:
        await event.reply(
            f"⏳ Please wait **{wait:.0f}s** before the next request.", parse_mode="md"
        )
        return

    url = match.group(1).rstrip(".,!?)];}")
    active_downloads.add(user_id)
    _user_cooldowns[user_id] = time.time()
    temporary = None
    status = None
    failure = None
    try:
        status = await event.reply("🎧 Preparing audio…")
        temporary = tempfile.TemporaryDirectory(prefix="botlite_voice_")
        async with download_semaphore:
            path, metadata = await download_audio(
                url,
                temporary.name,
                max_file_size=VOICE_MAX_FILE_SIZE,
                max_duration=VOICE_MAX_DURATION,
            )
        await get_voice_manager().play(event.chat_id, path, metadata["title"], temporary)
        temporary = None
    except Exception as exc:  # noqa: BLE001 - downloader and MTProto failures are source-specific
        failure = exc
    finally:
        active_downloads.discard(user_id)
        if temporary is not None:
            temporary.cleanup()

    if failure is not None:
        if status is None:
            log.error("Unable to prepare voice playback status: %s", failure)
        else:
            await status.edit(
                f"❌ Could not start voice playback. Ensure this group already has an active voice chat.\n"
                f"<code>{html.escape(str(failure)[:240])}</code>",
                parse_mode="html",
            )
        return

    await status.edit(
        f"🎶 Now playing: <b>{html.escape(metadata['title'])}</b>\n"
        "Run `/pause`, `/resume` or `/voice_stop` to control playback.",
        parse_mode="html",
    )


@client.on(events.NewMessage(pattern=r"^/(pause|resume|voice_stop)(?:@\w+)?$"))
async def cmd_voice_control(event):
    if not VOICE_ENABLED or not event.is_group or not _group_allowed(event):
        return
    command = event.pattern_match.group(1)
    if command == "pause":
        changed = await get_voice_manager().pause(event.chat_id)
        message = "⏸ Playback paused." if changed else "No active playback in this group."
    elif command == "resume":
        changed = await get_voice_manager().resume(event.chat_id)
        message = "▶️ Playback resumed." if changed else "No paused playback in this group."
    else:
        changed = await get_voice_manager().stop(event.chat_id)
        message = "⏹ Playback stopped." if changed else "No active playback in this group."
    await event.reply(message)
