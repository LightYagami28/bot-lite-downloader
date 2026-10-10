"""
botlite.downloader
~~~~~~~~~~~~~~~~~~
Public API: download(url, tmpdir) → list[MediaResult]

Tries yt-dlp first; falls back to gallery-dl.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile

from botlite.downloader import gallery, ytdlp

log = logging.getLogger("botlite.downloader")

MediaResult = tuple[str, dict, str]  # (filepath, meta, mediatype)


async def download(url: str) -> tuple[str, list[MediaResult]]:
    """
    Download media from *url*.

    Returns (tmpdir, results). The caller is responsible for
    cleaning up tmpdir (shutil.rmtree) after sending files.

    Raises RuntimeError if both engines fail.
    """
    tmpdir = tempfile.mkdtemp(prefix="botlite_")

    try:
        ytdir = os.path.join(tmpdir, "yt")
        os.makedirs(ytdir, exist_ok=True)
        try:
            results = await ytdlp.download(url, ytdir)
            if results:
                return tmpdir, results
        except Exception as exc:  # noqa: BLE001 - isolate third-party extractor failures
            log.warning("[yt-dlp] failed (%s): %s", url, exc)

        gddir = os.path.join(tmpdir, "gd")
        os.makedirs(gddir, exist_ok=True)
        try:
            results = await gallery.download(url, gddir)
            if results:
                return tmpdir, results
        except Exception as exc:  # noqa: BLE001 - isolate third-party extractor failures
            log.warning("[gallery-dl] failed (%s): %s", url, exc)

        raise RuntimeError(
            "Both yt-dlp and gallery-dl could not extract media from this URL.\n"
            "The site may require cookies, or the content may be unavailable."
        )
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
