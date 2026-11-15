"""URL detection handler and upload pipeline."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time

from telethon import events
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo

from botlite import db
from botlite.client import (
    _user_cooldowns,
    active_downloads,
    client,
    download_semaphore,
)
from botlite.config import MAX_FILE_SIZE, MIN_FREE_DISK
from botlite.downloader import download
from botlite.errors import RECOVERABLE_ERRORS
from botlite.handlers.access import group_allowed
from botlite.utils.format import build_caption, fmt_size
from botlite.utils.system import check_cooldown, free_disk

log = logging.getLogger("botlite.url")

# Exclude t.me links; allow everything else
_URL_RE = re.compile(r"https?://(?!t\.me/)[^\s<>\"{}|\\^`\[\]]+")


# ── Media sender ──────────────────────────────────────────────────────────────


def _media_attributes(meta: dict, mtype: str) -> list:
    duration = int(meta.get("duration") or 0)
    if mtype == "video":
        return [
            DocumentAttributeVideo(
                duration=duration,
                w=int(meta.get("width") or 0),
                h=int(meta.get("height") or 0),
                supports_streaming=True,
            )
        ]
    if mtype == "audio":
        return [
            DocumentAttributeAudio(
                duration=duration,
                title=meta.get("title") or "",
                performer=meta.get("uploader") or "",
            )
        ]
    return []


async def _send_media(event, file_path: str, meta: dict, mtype: str) -> None:
    size = os.path.getsize(file_path)
    caption = build_caption(
        mtype, meta.get("title"), meta.get("uploader"), (meta.get("duration"), size)
    )
    kwargs: dict = {
        "caption": caption,
        "parse_mode": "md",
        "reply_to": event.message.id,
    }
    attributes = _media_attributes(meta, mtype)
    if attributes:
        kwargs["attributes"] = attributes

    await client.send_file(event.chat_id, file_path, **kwargs)


async def _safe_edit(msg, text: str) -> None:
    try:
        await msg.edit(text, parse_mode="md")
    except RECOVERABLE_ERRORS as exc:
        log.debug("Unable to edit status message: %s", exc)


# ── Guards ────────────────────────────────────────────────────────────────────


async def _check_guards(event, user_id: int) -> bool:
    """Return True if the request should be rejected."""
    if db.is_banned(user_id):
        await event.reply("🚫 You are banned from using this bot.")
        return True
    if user_id in active_downloads:
        await event.reply("⏳ Your previous download is still running. Please wait.")
        return True
    wait = check_cooldown(_user_cooldowns, user_id)
    if wait > 0:
        await event.reply(
            f"⏳ Please wait **{wait:.0f}s** before the next request.",
            parse_mode="md",
        )
        return True
    if free_disk() < MIN_FREE_DISK:
        log.warning("Disk space low (%s), rejecting download", fmt_size(free_disk()))
        await event.reply("⚠️ The server is running low on disk space. Try again later.")
        return True
    return False


# ── Upload loop ───────────────────────────────────────────────────────────────


def _remove_file(file_path: str) -> None:
    try:
        os.remove(file_path)
    except OSError as exc:
        log.debug("Unable to remove downloaded file %s: %s", file_path, exc)


async def _upload_one(event, status, item: tuple, position: tuple[int, int]) -> bool:
    """Upload a single result; return True when it was sent."""
    file_path, meta, mtype = item
    index, total = position
    size = os.path.getsize(file_path)
    if size > MAX_FILE_SIZE:
        await event.reply(
            f"⚠️ File {index}/{total} skipped — too large ({fmt_size(size)}).",
            parse_mode="md",
        )
        return False
    if total > 1:
        await _safe_edit(status, f"📤 **Uploading {index}/{total}…**")
    try:
        await _send_media(event, file_path, meta, mtype)
        return True
    except RECOVERABLE_ERRORS as exc:
        log.exception("Send failed for %s", file_path)
        await event.reply(
            f"❌ Failed to send file {index}: `{str(exc)[:150]}`",
            parse_mode="md",
        )
        return False
    finally:
        _remove_file(file_path)


async def _upload_results(event, status, results: list) -> int:
    total = len(results)
    await _safe_edit(status, f"📤 **Uploading {total} file{'s' if total > 1 else ''}…**")
    sent = 0
    for index, item in enumerate(results, 1):
        if await _upload_one(event, status, item, (index, total)):
            sent += 1
    return sent


# ── Handler ───────────────────────────────────────────────────────────────────


def _first_url(event) -> str | None:
    """Return the first media URL of a non-command message, if any."""
    text = event.message.text or event.message.caption or ""
    if text.lstrip().startswith("/"):
        return None
    urls = _URL_RE.findall(text)
    return urls[0] if urls else None


async def _finish(event, status, results: list) -> None:
    """Upload the results and report the outcome on the status message."""
    if not results:
        await _safe_edit(status, "❌ No media found at that URL.")
        db.increment("failed_downloads")
        return
    if await _upload_results(event, status, results) == 0:
        await _safe_edit(status, "❌ Could not send any files.")
        db.increment("failed_downloads")
        return
    db.increment("total_downloads")
    try:
        await status.delete()
    except RECOVERABLE_ERRORS as exc:
        log.debug("Unable to delete status message: %s", exc)


@client.on(events.NewMessage())
async def url_handler(event):
    """Download and send the first media URL found in a non-command message."""
    if not group_allowed(event):
        return
    url = _first_url(event)
    user_id = event.sender_id
    if url is None or await _check_guards(event, user_id):
        return

    _user_cooldowns[user_id] = time.time()
    active_downloads.add(user_id)
    status = await event.reply("⏳ **Fetching…**", parse_mode="md")
    tmpdir = None
    try:
        async with download_semaphore:
            tmpdir, results = await download(url)
        await _finish(event, status, results)
    except RECOVERABLE_ERRORS as exc:
        log.exception("Error for %s", url)
        await _safe_edit(status, f"❌ **Download failed.**\n\n`{str(exc)[:300]}`")
        db.increment("failed_downloads")
    finally:
        active_downloads.discard(user_id)
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
