"""
botlite.utils.format
~~~~~~~~~~~~~~~~~~~~
Human-readable formatting helpers.
"""

from __future__ import annotations


def fmt_size(n: float | None) -> str:
    if n is None:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_dur(secs: int | None) -> str:
    if not secs:
        return ""
    s = int(secs)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_uptime(secs: float) -> str:
    s = int(secs)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}h {m}m {sec}s"


def build_caption(mtype: str, title: str | None, uploader: str | None = None,
                  duration: int | None = None, size: int | None = None) -> str:
    icon  = {"video": "🎬", "audio": "🎵", "photo": "📸"}.get(mtype, "📎")
    lines = [f"{icon} **{title or 'Media'}**"]
    if uploader:
        lines.append(f"👤 {uploader}")
    meta = []
    if duration:
        meta.append(f"⏱ {fmt_dur(duration)}")
    if size:
        meta.append(f"📦 {fmt_size(size)}")
    if meta:
        lines.append("  ".join(meta))
    return "\n".join(lines)
