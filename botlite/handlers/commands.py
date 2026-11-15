"""Telegram command handlers: /start /help /status /stats /ban /unban and voice."""

from __future__ import annotations

import html
import logging
import os
import re
import tempfile
import time

from telethon import events
from telethon.tl import types
from telethon.tl.custom import Button

from botlite import VERSION, db
from botlite.client import _user_cooldowns, active_downloads, client, download_semaphore
from botlite.config import (
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
from botlite.errors import RECOVERABLE_ERRORS
from botlite.handlers.access import group_allowed
from botlite.utils.format import fmt_size, fmt_uptime
from botlite.utils.system import check_cooldown, free_disk
from botlite.voice import get_voice_manager

_start_time = time.time()
_VOICE_URL_RE = re.compile(r"^/play(?:@\w+)?\s+(https?://\S+)\s*$", re.IGNORECASE)
log = logging.getLogger("botlite.commands")


def is_sudo(uid: int) -> bool:
    """Return True when *uid* is configured as an admin."""
    return uid in SUDO_USERS


def _dashboard_button() -> list | None:
    """Return a one-row inline keyboard with the WebApp button, or None."""
    if not WEBAPP_PUBLIC_URL:
        return None
    try:
        return [
            [
                types.KeyboardInlineButton(
                    "📊 Open Dashboard",
                    types.InlineButtonTypeWebView(WEBAPP_PUBLIC_URL),
                )
            ]
        ]
    except (AttributeError, TypeError):
        return [[Button.url("📊 Open Dashboard", url=WEBAPP_PUBLIC_URL)]]


# ── /start ────────────────────────────────────────────────────────────────────


async def cmd_start(event):
    """Reply to /start with the bot introduction."""
    if not group_allowed(event):
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


_HELP_HEAD = (
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
)


def _help_text(is_group: bool) -> str:
    cooldown_line = f"• Cooldown between requests: {USER_COOLDOWN}s\n" if USER_COOLDOWN else ""
    voice_line = (
        "• In allowlisted groups: `/play URL`, `/pause`, `/resume`, `/voice_stop`\n"
        if VOICE_ENABLED and is_group
        else ""
    )
    return (
        f"{_HELP_HEAD}• Max file size: {fmt_size(MAX_FILE_SIZE)}\n"
        f"{cooldown_line}{voice_line}• Some sites actively block bots"
    )


async def cmd_help(event):
    """Reply to /help with usage, limits and cookie instructions."""
    if not group_allowed(event):
        return
    await event.reply(
        _help_text(event.is_group),
        parse_mode="md",
        link_preview=False,
        buttons=_dashboard_button(),
    )


# ── /status ───────────────────────────────────────────────────────────────────


async def cmd_status(event):
    """Reply to /status with uptime, active downloads and free disk."""
    if not group_allowed(event):
        return
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


async def cmd_stats(event):
    """Reply to /stats (sudo, private chat) with the download counters."""
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


async def cmd_ban(event):
    """Ban a user via /ban USER_ID (sudo, private chat)."""
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


async def cmd_unban(event):
    """Unban a user via /unban USER_ID (sudo, private chat)."""
    if not event.is_private or not is_sudo(event.sender_id):
        return
    match = event.pattern_match.group(1)
    if not match:
        await event.reply("Usage: `/unban USER_ID`", parse_mode="md")
        return
    uid = int(match.strip())
    db.unban(uid)
    await event.reply(f"✅ User `{uid}` unbanned.", parse_mode="md")


async def _voice_guard_reply(event, user_id: int) -> bool:
    """Reply and return True when the user may not start playback right now."""
    if db.is_banned(user_id):
        await event.reply("🚫 You are banned from using this bot.")
        return True
    if user_id in active_downloads:
        await event.reply("⏳ Your previous download is still running. Please wait.")
        return True
    wait = check_cooldown(_user_cooldowns, user_id)
    if wait > 0:
        await event.reply(
            f"⏳ Please wait **{wait:.0f}s** before the next request.", parse_mode="md"
        )
        return True
    return False


async def _download_voice_audio(url: str, dir_name: str):
    """Download the audio for voice playback under the shared semaphore."""
    async with download_semaphore:
        return await download_audio(
            url,
            dir_name,
            max_file_size=VOICE_MAX_FILE_SIZE,
            max_duration=VOICE_MAX_DURATION,
        )


def _cleanup_voice_temporary(temporary) -> None:
    """Delete the temporary directory when it still owns the audio file."""
    if temporary is not None:
        temporary.cleanup()


async def _prepare_and_play(event, url: str) -> tuple[dict | None, Exception | None, object]:
    """Download the audio and start playback; return (metadata, failure, status)."""
    temporary = None
    status = None
    try:
        status = await event.reply("🎧 Preparing audio…")
        temporary = tempfile.TemporaryDirectory(prefix="botlite_voice_")
        path, metadata = await _download_voice_audio(url, temporary.name)
        await get_voice_manager().play(
            event.chat_id, path, metadata["title"], temporary
        )
        temporary = None
    except RECOVERABLE_ERRORS as exc:
        return None, exc, status
    finally:
        _cleanup_voice_temporary(temporary)
    return metadata, None, status


async def _report_voice_failure(status, failure: Exception) -> None:
    if status is None:
        log.error("Unable to prepare voice playback status: %s", failure)
        return
    await status.edit(
        "❌ Could not start voice playback. "
        "Ensure this group already has an active voice chat.\n"
        f"<code>{html.escape(str(failure)[:240])}</code>",
        parse_mode="html",
    )


async def _play_from_url(event, url: str) -> None:
    user_id = event.sender_id
    active_downloads.add(user_id)
    _user_cooldowns[user_id] = time.time()
    try:
        metadata, failure, status = await _prepare_and_play(event, url)
    finally:
        active_downloads.discard(user_id)

    if failure is not None:
        await _report_voice_failure(status, failure)
        return

    await status.edit(
        f"🎶 Now playing: <b>{html.escape(metadata['title'])}</b>\n"
        "Run `/pause`, `/resume` or `/voice_stop` to control playback.",
        parse_mode="html",
    )


def _voice_group_allowed(event) -> bool:
    return VOICE_ENABLED and event.is_group and group_allowed(event)


async def cmd_voice_play(event):
    """Download and start voice playback via /play URL (allowlisted groups)."""
    if not _voice_group_allowed(event):
        return
    match = _VOICE_URL_RE.fullmatch((event.raw_text or "").strip())
    if match is None:
        await event.reply("Usage: `/play https://…`", parse_mode="md")
        return
    if await _voice_guard_reply(event, event.sender_id):
        return
    await _play_from_url(event, match.group(1).rstrip(".,!?)];}"))


_VOICE_CONTROLS = {
    "pause": ("pause", "⏸ Playback paused.", "No active playback in this group."),
    "resume": ("resume", "▶️ Playback resumed.", "No paused playback in this group."),
    "voice_stop": ("stop", "⏹ Playback stopped.", "No active playback in this group."),
}


async def cmd_voice_control(event):
    """Handle /pause, /resume and /voice_stop in groups."""
    if not _voice_group_allowed(event):
        return
    method, done, idle = _VOICE_CONTROLS[event.pattern_match.group(1)]
    changed = await getattr(get_voice_manager(), method)(event.chat_id)
    await event.reply(done if changed else idle)


client.add_event_handler(cmd_start, events.NewMessage(pattern="/start"))
client.add_event_handler(cmd_help, events.NewMessage(pattern="/help"))
client.add_event_handler(cmd_status, events.NewMessage(pattern="/status"))
client.add_event_handler(cmd_stats, events.NewMessage(pattern="/stats"))
client.add_event_handler(cmd_ban, events.NewMessage(pattern=r"/ban( \d+)?"))
client.add_event_handler(cmd_unban, events.NewMessage(pattern=r"/unban( \d+)?"))
client.add_event_handler(cmd_voice_play, events.NewMessage(pattern=r"^/play(?:@\w+)?(?:\s|$)"))
client.add_event_handler(cmd_voice_control, events.NewMessage(pattern=r"^/(pause|resume|voice_stop)(?:@\w+)?$"))
