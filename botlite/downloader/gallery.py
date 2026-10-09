"""
botlite.downloader.gallery
~~~~~~~~~~~~~~~~~~~~~~~~~~
Download media via gallery-dl (fallback for photo galleries/carousels).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from urllib.parse import urlsplit

from botlite.downloader.cookies import resolve as resolve_cookie
from botlite.downloader.ytdlp import _AUDIO_EXTS, _IMAGE_EXTS, _VIDEO_EXTS

log = logging.getLogger("botlite.gallery")

MediaResult = tuple[str, dict, str]


def _scan_files(tmpdir: str) -> list[MediaResult]:
    results = []
    for fname in sorted(os.listdir(tmpdir)):
        fp  = os.path.join(tmpdir, fname)
        ext = os.path.splitext(fname)[1].lower()
        if not os.path.isfile(fp) or os.path.getsize(fp) < 100:
            continue
        if ext in _VIDEO_EXTS:    mtype = "video"
        elif ext in _IMAGE_EXTS:  mtype = "photo"
        elif ext in _AUDIO_EXTS:  mtype = "audio"
        else:                     continue
        results.append((fp, {"size": os.path.getsize(fp)}, mtype))
    if not results:
        raise RuntimeError("gallery-dl produced no usable files")
    return results


async def download(url: str, tmpdir: str) -> list[MediaResult]:
    """Download via gallery-dl. Returns [(filepath, meta, mediatype), ...]."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("gallery-dl only accepts absolute HTTP(S) URLs")

    cookie_file = resolve_cookie(url)
    command = [
        sys.executable,
        "-m",
        "gallery_dl",
        "--directory",
        tmpdir,
        "--filename",
        "{num:>03}_{id}.{extension}",
        "--no-part",
    ]
    if cookie_file:
        command.extend(("--cookies", cookie_file))
    command.append(url)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        await process.communicate()
        raise TimeoutError("gallery-dl exceeded the 120-second request limit") from None

    # Exit code 1 can represent partial success; completed media remains usable.
    if process.returncode not in (0, 1):
        error = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"gallery-dl exited {process.returncode}: {error[:300]}")

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _scan_files, tmpdir)
