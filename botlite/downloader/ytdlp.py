"""Download media via yt-dlp."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Mapping
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from botlite.config import MAX_FILE_SIZE
from botlite.downloader.cookies import resolve as resolve_cookie

log = logging.getLogger("botlite.ytdlp")
_LOG_FMT = "[yt-dlp] %s"
_MIN_FILE_SIZE = 100  # ignore freshly written files smaller than this (bytes)

_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".m4v"}
_AUDIO_EXTS = {".mp3", ".m4a", ".ogg", ".opus", ".flac", ".wav", ".aac"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ALL_EXTS = _VIDEO_EXTS | _AUDIO_EXTS | _IMAGE_EXTS

MediaResult = tuple[str, dict, str]  # (filepath, meta, mediatype)


class _Logger:
    def debug(self, msg: str) -> None:
        """Forward a yt-dlp debug message to the botlite logger."""
        if not msg.startswith("[debug] "):
            log.debug(_LOG_FMT, msg)

    def info(self, msg: str) -> None:
        """Forward a yt-dlp info message to the botlite logger."""
        log.info(_LOG_FMT, msg)

    def warning(self, msg: str) -> None:
        """Forward a yt-dlp warning message to the botlite logger."""
        log.warning(_LOG_FMT, msg)

    def error(self, msg: str) -> None:
        """Forward a yt-dlp error message to the botlite logger."""
        log.error(_LOG_FMT, msg)


def _guess_mtype(path: str) -> str:
    """Guess a media kind from a downloaded file extension.

    Args:
        path: Path of the downloaded file.

    Returns:
        One of ``"video"``, ``"audio"`` or ``"photo"`` (video by default).
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _IMAGE_EXTS:
        return "photo"
    return "video"


def _mtype_from_info(file_path: str, vcodec: str, acodec: str) -> str:
    """Derive the media kind from yt-dlp codec metadata and extension.

    Args:
        file_path: Path of the downloaded file.
        vcodec: Video codec reported by yt-dlp.
        acodec: Audio codec reported by yt-dlp.

    Returns:
        The detected media kind.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _IMAGE_EXTS:
        return "photo"
    for codec, mtype in ((vcodec, "video"), (acodec, "audio")):
        if codec and codec != "none":
            return mtype
    return _guess_mtype(file_path)


def _new_files(tmpdir: str, before: set[str]) -> list[str]:
    """List non-empty files created during a yt-dlp run.

    Args:
        tmpdir: Destination directory.
        before: File names present before the run.

    Returns:
        Paths of the newly written files.

    Raises:
        RuntimeError: When yt-dlp wrote no usable file.
    """
    paths = [os.path.join(tmpdir, name) for name in sorted(set(os.listdir(tmpdir)) - before)]
    new_files = [path for path in paths if os.path.getsize(path) > _MIN_FILE_SIZE]
    if not new_files:
        raise RuntimeError("yt-dlp finished but no file was written")
    return new_files


def _scan_new_files(
    tmpdir: str, before: set[str], meta: dict, codecs: tuple[str, str]
) -> list[MediaResult]:
    """Convert newly written files into media results.

    Args:
        tmpdir: Destination directory.
        before: File names present before the run.
        meta: Metadata shared by every result.
        codecs: Video and audio codecs reported by yt-dlp.

    Returns:
        One entry per supported downloaded file.
    """
    vcodec, acodec = codecs
    results = []
    for file_path in _new_files(tmpdir, before):
        if os.path.splitext(file_path)[1].lower() in ALL_EXTS:
            mtype = _mtype_from_info(file_path, vcodec, acodec)
            results.append((file_path, {**meta, "size": os.path.getsize(file_path)}, mtype))
    return results


_PREFERRED_VIDEO = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]"
_PREFERRED_MUXED = "best[ext=mp4][height<=1080]"
_VIDEO_FORMAT = f"{_PREFERRED_VIDEO}/{_PREFERRED_MUXED}/bestvideo+bestaudio/best"


def _base_opts(tmpdir: str, cookie_file: str | None, max_filesize: int) -> dict[str, Any]:
    """Build the shared yt-dlp option dictionary.

    Args:
        tmpdir: Destination directory.
        cookie_file: Optional path to a cookies file.
        max_filesize: Maximum accepted download size in bytes.

    Returns:
        yt-dlp configuration with network timeouts and retries.
    """
    opts = {
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "logger": _Logger(),
        "socket_timeout": 30,
        "retries": 3,
        "max_filesize": max_filesize,
        "writeinfojson": False,
        "writethumbnail": False,
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def _build_opts(tmpdir: str, cookie_file: str | None) -> dict[str, Any]:
    """Build yt-dlp options for a generic media download.

    Args:
        tmpdir: Destination directory.
        cookie_file: Optional path to a cookies file.

    Returns:
        yt-dlp configuration preferring 1080p MP4 with merged audio.
    """
    return {
        **_base_opts(tmpdir, cookie_file, MAX_FILE_SIZE),
        "format": _VIDEO_FORMAT,
        "merge_output_format": "mp4",
        "postprocessors": [],
    }


def _duration_filter(max_duration: int) -> Callable[..., str | None]:
    """Build a match filter that rejects unbounded or too-long audio.

    Args:
        max_duration: Maximum accepted duration in seconds.

    Returns:
        A yt-dlp match-filter callable returning a rejection reason or None.
    """
    def within_duration(info: dict, *, incomplete: bool) -> str | None:
        """Reject unknown or excessive durations before downloading."""
        duration = info.get("duration")
        if duration is None:
            if incomplete:
                return None
            return "Audio duration is unknown; refusing an unbounded voice-chat download"
        if duration > max_duration:
            return f"Audio exceeds the {max_duration}-second voice-chat limit"
        return None

    return within_duration


def _size_hook(max_file_size: int) -> Callable[[dict[str, Any]], None]:
    """Build a progress hook that aborts downloads exceeding the size limit.

    Args:
        max_file_size: Maximum accepted download size in bytes.

    Returns:
        A yt-dlp progress hook callable.
    """
    def enforce_download_size(progress: dict) -> None:
        """Abort the download as soon as the byte limit is exceeded."""
        if progress.get("downloaded_bytes", 0) > max_file_size:
            raise DownloadError(
                f"Audio exceeds the {max_file_size}-byte voice-chat limit"
            )

    return enforce_download_size


def _build_audio_opts(
    tmpdir: str,
    cookie_file: str | None,
    max_file_size: int,
    max_duration: int,
) -> dict[str, Any]:
    """Build yt-dlp options for a bounded voice-chat audio download.

    Args:
        tmpdir: Destination directory.
        cookie_file: Optional path to a cookies file.
        max_file_size: Maximum accepted download size in bytes.
        max_duration: Maximum accepted audio duration in seconds.

    Returns:
        yt-dlp configuration with duration and size guards.
    """
    return {
        **_base_opts(tmpdir, cookie_file, max_file_size),
        "format": "bestaudio/best",
        "match_filter": _duration_filter(max_duration),
        "progress_hooks": [_size_hook(max_file_size)],
    }


def _audio_path(ydl: yt_dlp.YoutubeDL, info: Mapping[str, Any], tmpdir: str) -> str:
    """Resolve the audio path produced by yt-dlp.

    Args:
        ydl: YoutubeDL instance used for the extraction.
        info: Extracted media information.
        tmpdir: Destination directory used as a fallback search location.

    Returns:
        Path of the downloaded audio file.

    Raises:
        RuntimeError: When the output file is ambiguous.
    """
    path = ydl.prepare_filename(info)
    if os.path.isfile(path):
        return path
    candidates = [
        os.path.join(tmpdir, name)
        for name in os.listdir(tmpdir)
        if os.path.isfile(os.path.join(tmpdir, name))
    ]
    if len(candidates) != 1:
        raise RuntimeError("yt-dlp did not produce one unambiguous audio file")
    return candidates[0]


def _checked_audio_size(path: str, max_file_size: int) -> int:
    """Validate the size of a downloaded audio file.

    Args:
        path: Path of the audio file.
        max_file_size: Maximum accepted size in bytes.

    Returns:
        The file size in bytes.

    Raises:
        ValueError: When the file exceeds the limit.
        RuntimeError: When the file is empty.
    """
    actual_size = os.path.getsize(path)
    if actual_size > max_file_size:
        raise ValueError("Downloaded audio exceeds the configured size limit")
    if not actual_size:
        raise RuntimeError("yt-dlp produced an empty audio file")
    return actual_size


async def download_audio(
    url: str,
    tmpdir: str,
    *,
    max_file_size: int,
    max_duration: int,
) -> tuple[str, dict]:
    """Download one bounded audio track for an explicitly enabled voice chat."""
    opts = _build_audio_opts(tmpdir, resolve_cookie(url), max_file_size, max_duration)
    loop = asyncio.get_running_loop()

    def _run() -> tuple[str, dict]:
        """Extract and bound the audio track inside the executor thread."""
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise RuntimeError("yt-dlp returned no audio information")
            path = _audio_path(ydl, info, tmpdir)
        return path, {
            "title": info.get("title") or "Untitled audio",
            "duration": info.get("duration"),
            "size": _checked_audio_size(path, max_file_size),
        }

    return await loop.run_in_executor(None, _run)


def _media_meta(info: Mapping[str, Any]) -> dict:
    """Select the metadata exposed to bot users.

    Args:
        info: Raw yt-dlp information dictionary.

    Returns:
        Normalized metadata dictionary.
    """
    return {
        "title": info.get("title"),
        "uploader": info.get("uploader") or info.get("channel"),
        "duration": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
    }


async def download(url: str, tmpdir: str) -> list[MediaResult]:
    """Download via yt-dlp. Returns [(filepath, meta, mediatype), ...]."""
    opts = _build_opts(tmpdir, resolve_cookie(url))
    loop = asyncio.get_running_loop()

    def _run() -> list[MediaResult]:
        """Extract media inside the executor thread and collect new files."""
        before = set(os.listdir(tmpdir))
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError("yt-dlp returned no info")
        codecs = (info.get("vcodec", ""), info.get("acodec", ""))
        return _scan_new_files(tmpdir, before, _media_meta(info), codecs)

    return await loop.run_in_executor(None, _run)
