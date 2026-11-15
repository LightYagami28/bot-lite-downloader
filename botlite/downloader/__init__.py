"""Public download API: try yt-dlp first, then fall back to gallery-dl."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile

from yt_dlp.utils import YoutubeDLError

from botlite.downloader import gallery, ytdlp

log = logging.getLogger("botlite.downloader")

MediaResult = tuple[str, dict, str]  # (filepath, meta, mediatype)


async def _attempt(url: str, spec: tuple) -> list[MediaResult]:
    engine, name, subdir, errors = spec
    os.makedirs(subdir, exist_ok=True)
    try:
        return await engine.download(url, subdir)
    except errors as exc:
        log.warning("[%s] failed (%s): %s", name, url, exc)
        return []


_YTDLP_ERRORS = (YoutubeDLError, RuntimeError, ValueError, OSError)
_GALLERY_ERRORS = (RuntimeError, ValueError, OSError)
_NO_MEDIA = (
    "Both yt-dlp and gallery-dl could not extract media from this URL.\n"
    "The site may require cookies, or the content may be unavailable."
)


async def _extract(url: str, tmpdir: str) -> list[MediaResult]:
    yt_spec = (ytdlp, "yt-dlp", os.path.join(tmpdir, "yt"), _YTDLP_ERRORS)
    gd_spec = (gallery, "gallery-dl", os.path.join(tmpdir, "gd"), _GALLERY_ERRORS)
    return await _attempt(url, yt_spec) or await _attempt(url, gd_spec)


async def download(url: str) -> tuple[str, list[MediaResult]]:
    """Download media from *url*.

    Returns (tmpdir, results). The caller is responsible for
    cleaning up tmpdir (shutil.rmtree) after sending files.

    Raises RuntimeError if both engines fail.
    """
    tmpdir = tempfile.mkdtemp(prefix="botlite_")
    try:
        results = await _extract(url, tmpdir)
        if not results:
            raise RuntimeError(_NO_MEDIA)
        return tmpdir, results
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
