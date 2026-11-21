"""Download media via gallery-dl (fallback for photo galleries and carousels)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
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

# gallery-dl is the only program this module may run. The interpreter and the
# ``-m`` switch are literals at the call site and the module name comes from a
# fixed allowlist; request data is passed as separate argv elements, never as a
# shell string.
_ALLOWED_COMMANDS = frozenset({"gallery_dl"})
_FILENAME_TEMPLATE = "{num:>03}_{id}.{extension}"
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def _allow_command(name: str) -> str:
    """Resolve a module name against the execution allowlist.

    Args:
        name: Candidate Python module to execute.

    Returns:
        The validated module name.

    Raises:
        ValueError: When the module is not on the allowlist.
    """
    if name not in _ALLOWED_COMMANDS:
        raise ValueError(f"gallery-dl command not allowed: {name!r}")
    return name


def _validated_arg(value: str, label: str) -> str:
    """Validate one argv element supplied by a request.

    ``create_subprocess_exec`` uses no shell, so a value cannot start a second
    command; control characters and a leading dash (which gallery-dl could
    parse as an option) are rejected anyway.

    Args:
        value: Candidate argv element.
        label: Name used in the error message.

    Returns:
        The validated argv element.

    Raises:
        ValueError: When the element is empty or unsafe.
    """
    if not value or _CONTROL_CHARACTERS.search(value) or value.startswith("-"):
        raise ValueError(f"invalid {label} for gallery-dl")
    return value


def _validated_url(url: str) -> str:
    """Validate an absolute HTTP(S) URL before passing it to gallery-dl.

    Args:
        url: Candidate download URL.

    Returns:
        The validated URL.

    Raises:
        ValueError: When the URL is not absolute HTTP(S) or has control chars.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("gallery-dl only accepts absolute HTTP(S) URLs")
    return _validated_arg(url, "URL")


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


def _command(url: str, tmpdir: str) -> tuple[str, ...]:
    """Build validated gallery-dl arguments after the static program prefix.

    Args:
        url: Absolute HTTP(S) URL to download.
        tmpdir: Destination directory for the downloaded files.

    Returns:
        Argument vector for an exec call (never a shell string).

    Raises:
        ValueError: When a request-supplied argument is unsafe.
    """
    validated_url = _validated_url(url)
    args = [
        "--directory",
        _validated_arg(os.path.abspath(tmpdir), "directory"),
        "--filename",
        _FILENAME_TEMPLATE,
        "--no-part",
    ]
    cookie_file = resolve_cookie(validated_url)
    if cookie_file:
        args.extend(("--cookies", _validated_arg(cookie_file, "cookie file")))
    args.append(validated_url)
    return tuple(args)


async def _run(args: tuple[str, ...]) -> None:
    """Execute gallery-dl with a timeout and validate its exit status.

    Args:
        args: Validated argument vector for ``asyncio.create_subprocess_exec``.

    Returns:
        None.

    Raises:
        TimeoutError: When the subprocess exceeds the request limit.
        RuntimeError: When the subprocess exits with an unexpected code.
        ValueError: When the requested command is not on the allowlist.
    """
    module = _allow_command("gallery_dl")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        module,
        *args,
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
    await _run(_command(url, tmpdir))
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _scan_files, tmpdir)
