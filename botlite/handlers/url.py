"""URL detection handler and upload pipeline."""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from typing import Any

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

_URL_RE = re.compile(r"https?://(?!t\.me/)[^\s<>\"{}|\\^`\[\]]+")

MediaItem = tuple[str, dict[str, Any], str]
"""A downloaded media file: ``(filepath, meta, mediatype)``."""


async def _check_guards(event: Any, user_id: int) -> bool:
    """Check ban list, cooldown, in-flight state and free disk space.

    Args:
        event: Telegram event used to reply when the request is rejected.
        user_id: Telegram user identifier to check.

    Returns:
        ``True`` when the request must be rejected, ``False`` when accepted.
    """
    if db.is_banned(user_id):
        await event.reply("?? You are banned from using this bot.")
        return True
    if user_id in active_downloads:
        await event.reply("? Your previous download is still running. Please wait.")
        return True
    wait = check_cooldown(_user_cooldowns, user_id)
    if wait > 0:
        await event.reply(
            f"? Please wait **{wait:.0f}s** before the next request.",
            parse_mode="md",
        )
        return True
    if free_disk() < MIN_FREE_DISK:
        log.warning("Disk space low (%s), rejecting download", fmt_size(free_disk()))
        await event.reply("?? The server is running low on disk space. Try again later.")
        return True
    return False


def _int_field(meta: dict[str, Any], key: str) -> int:
    """Read an integer metadata field, defaulting to zero.

    Args:
        meta: Media metadata mapping.
        key: Metadata key to read.

    Returns:
        Integer metadata value (0 when missing or not numeric).
    """
    try:
        return int(meta.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _video_attributes(meta: dict[str, Any]) -> list[DocumentAttributeVideo]:
    """Build Telethon video attributes from media metadata.

    Args:
        meta: Media metadata mapping.

    Returns:
        List of video attributes (empty when metadata is unusable).
    """
    return [
        DocumentAttributeVideo(
            duration=_int_field(meta, "duration"),
            w=_int_field(meta, "width"),
            h=_int_field(meta, "height"),
            supports_streaming=True,
        )
    ]


def _audio_attributes(meta: dict[str, Any]) -> list[DocumentAttributeAudio]:
    """Build Telethon audio attributes from media metadata.

    Args:
        meta: Media metadata mapping.

    Returns:
        List of audio attributes (empty when metadata is unusable).
    """
    return [
        DocumentAttributeAudio(
            duration=_int_field(meta, "duration"),
            title=str(meta.get("title") or ""),
            performer=str(meta.get("uploader") or ""),
        )
    ]


_ATTRIBUTE_BUILDERS: dict[str, Any] = {
    "video": _video_attributes,
    "audio": _audio_attributes,
}


def _media_attributes(meta: dict[str, Any], mtype: str) -> list[Any]:
    """Pick the attribute builder for the media type, if any.

    Args:
        meta: Media metadata mapping.
        mtype: Media type keyword.

    Returns:
        Attribute list for the media type (possibly empty).
    """
    builder = _ATTRIBUTE_BUILDERS.get(mtype)
    return builder(meta) if builder else []


async def _send_media(
    event: Any,
    file_path: str,
    meta: dict[str, Any],
    mtype: str,
) -> None:
    """Send the downloaded media file with its caption and attributes.

    Args:
        event: Telegram event receiving the file.
        file_path: Local path of the downloaded file.
        meta: Media metadata for the caption.
        mtype: Media type keyword.
    """
    size = os.path.getsize(file_path)
    caption = build_caption(
        mtype, meta.get("title"), meta.get("uploader"), (meta.get("duration"), size)
    )
    kwargs: dict[str, Any] = {
        "caption": caption,
        "parse_mode": "md",
        "reply_to": event.message.id,
    }
    attributes = _media_attributes(meta, mtype)
    if attributes:
        kwargs["attributes"] = attributes
    await client.send_file(event.chat_id, file_path, **kwargs)


async def _safe_edit(msg: Any, text: str) -> None:
    """Edit a message, tolerating recoverable Telegram failures.

    Args:
        msg: Message to edit.
        text: New text content.
    """
    try:
        await msg.edit(text, parse_mode="md")
    except RECOVERABLE_ERRORS as exc:
        log.debug("Unable to edit status message: %s", exc)


def _remove_file(file_path: str) -> None:
    """Delete a temporary file, logging instead of raising.

    Args:
        file_path: Path of the file to remove.
    """
    try:
        os.remove(file_path)
    except OSError as exc:
        log.debug("Unable to remove downloaded file %s: %s", file_path, exc)


async def _reject_oversize(event: Any, size: int, position: tuple[int, int]) -> bool:
    """Reject files above the configured maximum size.

    Args:
        event: Telegram event receiving the reply.
        size: File size in bytes.
        position: Tuple ``(index, total)`` of the file in the batch.

    Returns:
        ``True`` when the file was rejected (reply sent), ``False`` when accepted.
    """
    if size <= MAX_FILE_SIZE:
        return False
    index, total = position
    await event.reply(
        f"? File {index}/{total} skipped — too large ({fmt_size(size)}).",
        parse_mode="md",
    )
    return True


async def _upload_one(event: Any, status: Any, item: MediaItem, position: tuple[int, int]) -> bool:
    """Upload a single media item, returning whether it was sent.

    Args:
        event: Telegram event receiving the file.
        status: Status message used for progress edits.
        item: Tuple ``(filepath, meta, mediatype)``.
        position: Tuple ``(index, total)`` of the item in the batch.

    Returns:
        ``True`` when the file was sent, ``False`` when skipped or failed.
    """
    file_path, meta, mtype = item
    index, total = position
    try:
        if await _reject_oversize(event, os.path.getsize(file_path), position):
            return False
        if total > 1:
            await _safe_edit(status, f"? **Uploading {index}/{total}.**")
        await _send_media(event, file_path, meta, mtype)
        return True
    except RECOVERABLE_ERRORS as exc:
        log.exception("Send failed for %s", file_path)
        await event.reply(
            f"? Failed to send file {index}: `{str(exc)[:150]}`",
            parse_mode="md",
        )
        return False
    finally:
        _remove_file(file_path)


async def _upload_results(event: Any, status: Any, results: list[MediaItem]) -> int:
    """Upload every media item, returning the number of files sent.

    Args:
        event: Telegram event receiving the files.
        status: Status message used for progress edits.
        results: List of ``(filepath, meta, mediatype)`` tuples.

    Returns:
        Count of files successfully sent.
    """
    total = len(results)
    await _safe_edit(status, f"? **Uploading {total} file{'s' if total > 1 else ''}.**")
    sent = 0
    for index, item in enumerate(results, 1):
        if await _upload_one(event, status, item, (index, total)):
            sent += 1
    return sent


def _first_url(event: Any) -> str | None:
    """Return the first media URL of a non-command message, if any.

    Args:
        event: Telegram event to inspect.

    Returns:
        First HTTP(S) URL found in text/caption, or ``None``.
    """
    text = event.message.text or event.message.caption or ""
    if text.lstrip().startswith("/"):
        return None
    urls = _URL_RE.findall(text)
    return urls[0] if urls else None


async def _finish(event: Any, status: Any, results: list[MediaItem]) -> None:
    """Upload the results and report the outcome on the status message.

    Args:
        event: Telegram event receiving the files.
        status: Status message used for the outcome edit.
        results: List of ``(filepath, meta, mediatype)`` tuples.
    """
    if not results:
        await _safe_edit(status, "? No media found at that URL.")
        db.increment("failed_downloads")
        return
    if not await _upload_results(event, status, results):
        await _safe_edit(status, "? Could not send any files.")
        db.increment("failed_downloads")
        return
    db.increment("total_downloads")
    try:
        await status.delete()
    except RECOVERABLE_ERRORS as exc:
        log.debug("Unable to delete status message: %s", exc)


async def _handle_url(event: Any, url: str, user_id: int) -> None:
    """Download a media URL and send it, honouring the download semaphore.

    Args:
        event: Telegram event receiving the file.
        url: Media URL to download.
        user_id: Telegram user identifier performing the request.
    """
    _user_cooldowns[user_id] = time.time()
    active_downloads.add(user_id)
    status = await event.reply("? **Fetching.**", parse_mode="md")
    tmpdir: str | None = None
    try:
        async with download_semaphore:
            tmpdir, results = await download(url)
        await _finish(event, status, results)
    except RECOVERABLE_ERRORS as exc:
        log.exception("Error for %s", url)
        await _safe_edit(status, f"? **Download failed.**\n\n`{str(exc)[:300]}`")
        db.increment("failed_downloads")
    finally:
        active_downloads.discard(user_id)
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


async def url_handler(event: Any) -> None:
    """Download and send the first media URL found in a non-command message.

    Args:
        event: Telegram event to handle.
    """
    url = _first_url(event) if group_allowed(event) else None
    if url is not None and not await _check_guards(event, event.sender_id):
        await _handle_url(event, url, event.sender_id)
