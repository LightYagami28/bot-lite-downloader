"""
botlite.downloader.gallery
~~~~~~~~~~~~~~~~~~~~~~~~~~
Download media via gallery-dl (fallback for photo galleries/carousels).
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess

from botlite.downloader.cookies import resolve as resolve_cookie
from botlite.downloader.ytdlp import _AUDIO_EXTS, _IMAGE_EXTS, _VIDEO_EXTS

log = logging.getLogger("botlite.gallery")

MediaResult = tuple[str, dict, str]


def _scan_files(tmpdir: str, stderr: str) -> list[MediaResult]:
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
        raise RuntimeError(f"gallery-dl produced no usable files.\n{stderr[:200]}")
    return results


async def download(url: str, tmpdir: str) -> list[MediaResult]:
    """Download via gallery-dl. Returns [(filepath, meta, mediatype), ...]."""
    cmd = [
        "gallery-dl",
        "--directory", tmpdir,
        "--filename",  "{num:>03}_{id}.{extension}",
        "--no-part",
    ]
    cookie_file = resolve_cookie(url)
    if cookie_file:
        cmd += ["--cookies", cookie_file]
    cmd.append(url)

    loop = asyncio.get_running_loop()

    def _run() -> list[MediaResult]:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        # exit code 1 = partial success — still usable
        if proc.returncode not in (0, 1):
            raise RuntimeError(
                f"gallery-dl exited {proc.returncode}: {proc.stderr[:300]}"
            )
        return _scan_files(tmpdir, proc.stderr)

    return await loop.run_in_executor(None, _run)
