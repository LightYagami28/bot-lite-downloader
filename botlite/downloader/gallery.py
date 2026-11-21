"""Download media via gallery-dl (fallback for photo galleries and carousels)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
from urllib.parse import urlsplit

from botlite.downloader.cookies import resolve as resolve_cookie
from botlite.downloader.ytdlp import (
    _AUDIO_EXTS,
    _IMAGE_EXTS,
    _MIN_FILE_SIZE,
    _VIDEO_EXTS,
)

log = logging.getLogger("botlite.gallery")

MediaResult = tuple[str, dict, str]


def _media_type(ext: str) -> str | None:
    """Map a lowercase file extension to a media kind.

    Args:
        ext: File extension including the leading dot.

    Returns:
        ``"video"``, ``"photo"``, ``"audio"`` or ``None`` when unsupported.
    """
    for extensions, mtype in (
        (_VIDEO_EXTS, "video"),
        (_IMAGE_EXTS, "photo"),
        (_AUDIO_EXTS, "audio"),
    ):
        if ext in extensions:
            return mtype
    return None


def _usable_result(tmpdir: str, name: str) -> MediaResult | None:
    """Build a result for a non-empty, supported downloaded file.

    Args:
        tmpdir: Directory that holds the downloaded files.
        name: File name to inspect.

    Returns:
        A media result, or ``None`` when the file is missing or too small.
    """
    file_path = os.path.join(tmpdir, name)
    mtype = _media_type(os.path.splitext(name)[1].lower())
    if mtype is None or not os.path.isfile(file_path):
        return None
    size = os.path.getsize(file_path)
    return (file_path, {"size": size}, mtype) if size >= _MIN_FILE_SIZE else None


def _scan_files(tmpdir: str) -> list[MediaResult]:
    """Collect every usable file produced by gallery-dl.

    Args:
        tmpdir: Directory that holds the downloaded files.

    Returns:
        List of usable media results.

    Raises:
        RuntimeError: When gallery-dl produced no usable files.
    """
    candidates = (_usable_result(tmpdir, name) for name in sorted(os.listdir(tmpdir)))
    results = [result for result in candidates if result is not None]
    if not results:
        raise RuntimeError("gallery-dl produced no usable files")
    return results


def _command(url: str, tmpdir: str) -> list[str]:
    """Build the gallery-dl argument vector, adding cookies when available.

    Args:
        url: Absolute HTTP(S) URL to download.
        tmpdir: Destination directory for the downloaded files.

    Returns:
        Argument vector for an exec call (never a shell string).
    """
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
    cookie_file = resolve_cookie(url)
    if cookie_file:
        command.extend(("--cookies", cookie_file))
    command.append(url)
    return command


async def _run(command: list[str]) -> None:
    """Execute gallery-dl with a timeout and validate its exit status.

    Args:
        command: Argument vector for ``asyncio.create_subprocess_exec``.

    Returns:
        None.

    Raises:
        TimeoutError: When the subprocess exceeds the request limit.
        RuntimeError: When the subprocess exits with an unexpected code.
    """
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.communicate()
        raise TimeoutError("gallery-dl exceeded the 120-second request limit") from None

    # Exit code 1 can represent partial success; completed media remains usable.
    if process.returncode not in (0, 1):
        error = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"gallery-dl exited {process.returncode}: {error[:300]}")


async def download(url: str, tmpdir: str) -> list[MediaResult]:
    """Download via gallery-dl. Returns [(filepath, meta, mediatype), ...]."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError("gallery-dl only accepts absolute HTTP(S) URLs")

    await _run(_command(url, tmpdir))
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _scan_files, tmpdir)
