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


async def _attempt(engine, name: str, url: str, subdir: str, errors: tuple) -> list[MediaResult]:
    os.makedirs(subdir, exist_ok=True)
    try:
        return await engine.download(url, subdir)
    except errors as exc:
        log.warning("[%s] failed (%s): %s", name, url, exc)
        return []


async def download(url: str) -> tuple[str, list[MediaResult]]:
    """
    Download media from *url*.

    Returns (tmpdir, results). The caller is responsible for
    cleaning up tmpdir (shutil.rmtree) after sending files.

    Raises RuntimeError if both engines fail.
    """
    tmpdir = tempfile.mkdtemp(prefix="botlite_")
    try:
        results = await _attempt(
            ytdlp,
            "yt-dlp",
            url,
            os.path.join(tmpdir, "yt"),
            (YoutubeDLError, RuntimeError, ValueError, OSError),
        ) or await _attempt(
            gallery,
            "gallery-dl",
            url,
            os.path.join(tmpdir, "gd"),
            (RuntimeError, ValueError, OSError),
        )
        if not results:
            raise RuntimeError(
                "Both yt-dlp and gallery-dl could not extract media from this URL.\n"
                "The site may require cookies, or the content may be unavailable."
            )
        return tmpdir, results
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
