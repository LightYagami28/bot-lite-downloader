"""Human-readable formatting helpers."""

from __future__ import annotations

_BYTES_PER_UNIT = 1024


def fmt_size(size: float | None) -> str:
    """Format a byte count in human-readable units (B, KB, MB, …)."""
    if size is None:
        return "Unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if size < _BYTES_PER_UNIT:
            return f"{size:.1f} {unit}"
        size /= _BYTES_PER_UNIT
    return f"{size:.1f} TB"


def fmt_dur(secs: int | None) -> str:
    """Format a duration as H:MM:SS (M:SS below one hour); empty for falsy input."""
    if not secs:
        return ""
    total = int(secs)
    hours, minutes, sec = total // 3600, (total % 3600) // 60, total % 60
    return f"{hours}:{minutes:02d}:{sec:02d}" if hours else f"{minutes}:{sec:02d}"


def fmt_uptime(secs: float) -> str:
    """Format seconds as ``Xh Ym Zs``."""
    total = int(secs)
    hours, minutes, sec = total // 3600, (total % 3600) // 60, total % 60
    return f"{hours}h {minutes}m {sec}s"


def _details_line(duration: int | None, size: int | None) -> str:
    parts = [
        text
        for text in (
            f"⏱ {fmt_dur(duration)}" if duration else "",
            f"📦 {fmt_size(size)}" if size else "",
        )
        if text
    ]
    return "  ".join(parts)


def build_caption(
    mtype: str,
    title: str | None,
    uploader: str | None = None,
    details: tuple[int | None, int | None] = (None, None),
) -> str:
    """Build the Markdown caption; *details* is ``(duration, size)``."""
    icon = {"video": "🎬", "audio": "🎵", "photo": "📸"}.get(mtype, "📎")
    lines = [f"{icon} **{title or 'Media'}**"]
    if uploader:
        lines.append(f"👤 {uploader}")
    details_line = _details_line(*details)
    if details_line:
        lines.append(details_line)
    return "\n".join(lines)
