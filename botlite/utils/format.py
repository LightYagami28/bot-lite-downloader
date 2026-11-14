"""Human-readable formatting helpers."""

from __future__ import annotations

_BYTES_PER_UNIT = 1024


def fmt_size(n: float | None) -> str:
    """Format a byte count in human-readable units (B, KB, MB, …)."""
    if n is None:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if n < _BYTES_PER_UNIT:
            return f"{n:.1f} {unit}"
        n /= _BYTES_PER_UNIT
    return f"{n:.1f} TB"


def fmt_dur(secs: int | None) -> str:
    """Format a duration as H:MM:SS (M:SS below one hour); empty for falsy input."""
    if not secs:
        return ""
    s = int(secs)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_uptime(secs: float) -> str:
    """Format seconds as ``Xh Ym Zs``."""
    s = int(secs)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}h {m}m {sec}s"


def build_caption(
    mtype: str,
    title: str | None,
    uploader: str | None = None,
    duration: int | None = None,
    size: int | None = None,
) -> str:
    """Build the Markdown caption for one downloaded media item."""
    icon = {"video": "🎬", "audio": "🎵", "photo": "📸"}.get(mtype, "📎")
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
