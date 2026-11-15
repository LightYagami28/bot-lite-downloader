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


async def download(url: str) -> tuple[str, list[MediaResult]]:
    """Download media from *url*.

    Returns (tmpdir, results). The caller is responsible for
    cleaning up tmpdir (shutil.rmtree) after sending files.

    Raises RuntimeError if both engines fail.
    """
    tmpdir = tempfile.mkdtemp(prefix="botlite_")
    try:
        results = await _attempt(
            url,
            (
                ytdlp,
                "yt-dlp",
                os.path.join(tmpdir, "yt"),
                (YoutubeDLError, RuntimeError, ValueError, OSError),
            ),
        ) or await _attempt(
            url,
            (
                gallery,
                "gallery-dl",
                os.path.join(tmpdir, "gd"),
                (RuntimeError, ValueError, OSError),
            ),
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
