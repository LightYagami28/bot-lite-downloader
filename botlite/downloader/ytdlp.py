"""
botlite.downloader.ytdlp
~~~~~~~~~~~~~~~~~~~~~~~~
Download media via yt-dlp.
"""

from __future__ import annotations

import asyncio
import logging
import os

import yt_dlp

from botlite.config import MAX_FILE_SIZE
from botlite.downloader.cookies import resolve as resolve_cookie

log = logging.getLogger("botlite.ytdlp")
_LOG_FMT = "[yt-dlp] %s"

_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv", ".m4v"}
_AUDIO_EXTS = {".mp3", ".m4a", ".ogg", ".opus", ".flac", ".wav", ".aac"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ALL_EXTS    = _VIDEO_EXTS | _AUDIO_EXTS | _IMAGE_EXTS

MediaResult = tuple[str, dict, str]   # (filepath, meta, mediatype)


class _Logger:
    def debug(self, msg: str) -> None:
        if not msg.startswith("[debug] "):
            log.debug(_LOG_FMT, msg)

    def info(self, msg: str) -> None:
        log.info(_LOG_FMT, msg)

    def warning(self, msg: str) -> None:
        log.warning(_LOG_FMT, msg)

    def error(self, msg: str) -> None:
        log.error(_LOG_FMT, msg)


def _guess_mtype(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in _VIDEO_EXTS: return "video"
    if ext in _AUDIO_EXTS: return "audio"
    if ext in _IMAGE_EXTS: return "photo"
    return "video"


def _mtype_from_info(fp: str, vcodec: str, acodec: str) -> str:
    ext = os.path.splitext(fp)[1].lower()
    if ext in _IMAGE_EXTS:             return "photo"
    if vcodec and vcodec != "none":    return "video"
    if acodec and acodec != "none":    return "audio"
    return _guess_mtype(fp)


def _scan_new_files(tmpdir: str, before: set[str], meta: dict,
                    vcodec: str, acodec: str) -> list[MediaResult]:
    new_files = [
        os.path.join(tmpdir, f)
        for f in sorted(set(os.listdir(tmpdir)) - before)
        if os.path.getsize(os.path.join(tmpdir, f)) > 100
    ]
    if not new_files:
        raise RuntimeError("yt-dlp finished but no file was written")

    results = []
    for fp in new_files:
        if os.path.splitext(fp)[1].lower() not in ALL_EXTS:
            continue
        mtype = _mtype_from_info(fp, vcodec, acodec)
        results.append((fp, {**meta, "size": os.path.getsize(fp)}, mtype))
    return results


def _build_opts(tmpdir: str, cookie_file: str | None) -> dict:
    opts = {
        "format": (
            "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]"
            "/best[ext=mp4][height<=1080]"
            "/bestvideo+bestaudio/best"
        ),
        "merge_output_format": "mp4",
        "outtmpl":             os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "noplaylist":          True,
        "quiet":               True,
        "no_warnings":         False,
        "logger":              _Logger(),
        "socket_timeout":      30,
        "retries":             3,
        "max_filesize":        MAX_FILE_SIZE,
        "writeinfojson":       False,
        "writethumbnail":      False,
        "postprocessors":      [],
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def _build_audio_opts(
    tmpdir: str,
    cookie_file: str | None,
    max_file_size: int,
    max_duration: int,
) -> dict:
    def within_duration(info: dict, *, incomplete: bool) -> str | None:
        duration = info.get("duration")
        if duration is None:
            if incomplete:
                return None
            return "Audio duration is unknown; refusing an unbounded voice-chat download"
        if duration > max_duration:
            return f"Audio exceeds the {max_duration}-second voice-chat limit"
        return None

    def enforce_download_size(progress: dict) -> None:
        if progress.get("downloaded_bytes", 0) > max_file_size:
            raise yt_dlp.utils.DownloadError(
                f"Audio exceeds the {max_file_size}-byte voice-chat limit"
            )

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(tmpdir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "logger": _Logger(),
        "socket_timeout": 30,
        "retries": 3,
        "max_filesize": max_file_size,
        "match_filter": within_duration,
        "progress_hooks": [enforce_download_size],
        "writeinfojson": False,
        "writethumbnail": False,
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


async def download_audio(
    url: str,
    tmpdir: str,
    *,
    max_file_size: int,
    max_duration: int,
) -> tuple[str, dict]:
    """Download one bounded audio track for an explicitly enabled voice chat."""
    opts = _build_audio_opts(
        tmpdir, resolve_cookie(url), max_file_size, max_duration
    )
    loop = asyncio.get_running_loop()

    def _run() -> tuple[str, dict]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                raise RuntimeError("yt-dlp returned no audio information")
            path = ydl.prepare_filename(info)
        if not os.path.isfile(path):
            candidates = [
                os.path.join(tmpdir, name)
                for name in os.listdir(tmpdir)
                if os.path.isfile(os.path.join(tmpdir, name))
            ]
            if len(candidates) != 1:
                raise RuntimeError("yt-dlp did not produce one unambiguous audio file")
            path = candidates[0]
        actual_size = os.path.getsize(path)
        if actual_size > max_file_size:
            raise ValueError("Downloaded audio exceeds the configured size limit")
        if not actual_size:
            raise RuntimeError("yt-dlp produced an empty audio file")
        return path, {
            "title": info.get("title") or "Untitled audio",
            "duration": info.get("duration"),
            "size": actual_size,
        }

    return await loop.run_in_executor(None, _run)


async def download(url: str, tmpdir: str) -> list[MediaResult]:
    """Download via yt-dlp. Returns [(filepath, meta, mediatype), ...]."""
    opts = _build_opts(tmpdir, resolve_cookie(url))
    loop = asyncio.get_running_loop()

    def _run() -> list[MediaResult]:
        before = set(os.listdir(tmpdir))
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        if info is None:
            raise RuntimeError("yt-dlp returned no info")
        meta = {
            "title":    info.get("title"),
            "uploader": info.get("uploader") or info.get("channel"),
            "duration": info.get("duration"),
            "width":    info.get("width"),
            "height":   info.get("height"),
        }
        return _scan_new_files(
            tmpdir, before, meta,
            info.get("vcodec", ""),
            info.get("acodec", ""),
        )

    return await loop.run_in_executor(None, _run)
