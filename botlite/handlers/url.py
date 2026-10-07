"""
botlite.handlers.url
~~~~~~~~~~~~~~~~~~~~
URL detection handler + upload pipeline.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
import traceback

from telethon import events
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo

from botlite import db
from botlite.client import (
    _user_cooldowns,
    active_downloads,
    client,
    download_semaphore,
)
from botlite.config import ALLOW_GROUPS, MAX_FILE_SIZE, MIN_FREE_DISK
from botlite.downloader import download
from botlite.utils.format import build_caption, fmt_size
from botlite.utils.system import check_cooldown, free_disk

log = logging.getLogger("botlite.url")

# Exclude t.me links; allow everything else
_URL_RE = re.compile(r"https?://(?!t\.me/)[^\s<>\"{}|\\^`\[\]]+")


# ── Media sender ──────────────────────────────────────────────────────────────

async def _send_media(event, fp: str, meta: dict, mtype: str) -> None:
    size    = os.path.getsize(fp)
    caption = build_caption(mtype, meta.get("title"), meta.get("uploader"),
                             meta.get("duration"), size)
    kwargs: dict = {"caption": caption, "parse_mode": "md",
                    "reply_to": event.message.id}

    if mtype == "video":
        kwargs["attributes"] = [DocumentAttributeVideo(
            duration          = int(meta.get("duration") or 0),
            w                 = int(meta.get("width")    or 0),
            h                 = int(meta.get("height")   or 0),
            supports_streaming= True,
        )]
    elif mtype == "audio":
        kwargs["attributes"] = [DocumentAttributeAudio(
            duration  = int(meta.get("duration") or 0),
            title     = meta.get("title")    or "",
            performer = meta.get("uploader") or "",
        )]

    await client.send_file(event.chat_id, fp, **kwargs)


async def _safe_edit(msg, text: str) -> None:
    try:
        await msg.edit(text, parse_mode="md")
    except Exception:
        pass


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

async def _upload_results(event, status, results: list) -> int:
    total = len(results)
    await _safe_edit(status, f"📤 **Uploading {total} file{'s' if total > 1 else ''}…**")

    sent = 0
    for i, (fp, meta, mtype) in enumerate(results, 1):
        size = os.path.getsize(fp)
        if size > MAX_FILE_SIZE:
            await event.reply(
                f"⚠️ File {i}/{total} skipped — too large ({fmt_size(size)}).",
                parse_mode="md",
            )
            continue
        if total > 1:
            await _safe_edit(status, f"📤 **Uploading {i}/{total}…**")
        try:
            await _send_media(event, fp, meta, mtype)
            sent += 1
        except Exception as exc:
            log.error("Send failed for %s: %s", fp, exc)
            await event.reply(
                f"❌ Failed to send file {i}: `{str(exc)[:150]}`",
                parse_mode="md",
            )
        finally:
            try:
                os.remove(fp)
            except Exception:
                pass
    return sent


# ── Handler ───────────────────────────────────────────────────────────────────

@client.on(events.NewMessage())
async def url_handler(event):
    if not event.is_private and not ALLOW_GROUPS:
        return

    text = event.message.text or event.message.caption or ""
    urls = _URL_RE.findall(text)
    if not urls:
        return

    url     = urls[0]
    user_id = event.sender_id

    if await _check_guards(event, user_id):
        return

    _user_cooldowns[user_id] = time.time()
    active_downloads.add(user_id)
    status = await event.reply("⏳ **Fetching…**", parse_mode="md")
    tmpdir = None

    try:
        async with download_semaphore:
            tmpdir, results = await download(url)

        if not results:
            await _safe_edit(status, "❌ No media found at that URL.")
            db.increment("failed_downloads")
            return

        sent = await _upload_results(event, status, results)

        if sent > 0:
            db.increment("total_downloads")
            try:
                await status.delete()
            except Exception:
                pass
        else:
            await _safe_edit(status, "❌ Could not send any files.")
            db.increment("failed_downloads")

    except Exception as exc:
        log.error("Error for %s:\n%s", url, traceback.format_exc())
        await _safe_edit(status, f"❌ **Download failed.**\n\n`{str(exc)[:300]}`")
        db.increment("failed_downloads")

    finally:
        active_downloads.discard(user_id)
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
