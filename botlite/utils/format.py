"""Human-readable formatting helpers for bot messages and status lines."""

from __future__ import annotations

_BYTES_PER_UNIT = 1024
_SIZE_UNITS: tuple[str, ...] = ("B", "KB", "MB", "GB", "TB")
_MEDIA_ICONS: dict[str, str] = {"video": "🎬", "audio": "🎵", "photo": "🖼️"}
_UPLOADER_ICON = "👤"
_FALLBACK_ICON = "📎"
_DURATION_ICON = "⏱"
_SIZE_ICON = "📦"


def fmt_size(size: float | None) -> str:
    """Format a byte count in human-readable units.

    Args:
        size: Byte count to format, or ``None`` for unknown values.

    Returns:
        Human-readable size such as ``"512.0 B"`` or ``"2.5 TB"``.
    """
    if size is None:
        return "Unknown"
    value = float(size)
    index = 0
    while value >= _BYTES_PER_UNIT and index < len(_SIZE_UNITS) - 1:
        value /= _BYTES_PER_UNIT
        index += 1
    return f"{value:.1f} {_SIZE_UNITS[index]}"


def fmt_dur(secs: int | None) -> str:
    """Format a duration as ``H:MM:SS`` (or ``M:SS`` below one hour).

    Args:
        secs: Duration in seconds; falsy values produce an empty string.

    Returns:
        Human-readable duration such as ``"1:01:01"``.
    """
    if not secs:
        return ""
    total = int(secs)
    hours, minutes, seconds = total // 3600, (total % 3600) // 60, total % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def fmt_uptime(secs: float) -> str:
    """Format seconds of uptime as ``Xh Ym Zs``.

    Args:
        secs: Uptime in seconds.

    Returns:
        Human-readable uptime such as ``"1h 1m 1s"``.
    """
    total = int(secs)
    hours, minutes, seconds = total // 3600, (total % 3600) // 60, total % 60
    return f"{hours}h {minutes}m {seconds}s"


def _details_line(duration: int | None, size: int | None) -> str:
    """Build the optional duration/size details line of a caption.

    Args:
        duration: Media duration in seconds, if known.
        size: Media size in bytes, if known.

    Returns:
        Details fragment such as ``"  ⏱ 1:15  📦 2.0 KB"``, or an empty string.
    """
    parts: list[str] = []
    if duration:
        parts.append(f"{_DURATION_ICON} {fmt_dur(duration)}")
    if size:
        parts.append(f"{_SIZE_ICON} {fmt_size(size)}")
    return "  ".join(parts)


def build_caption(
    mtype: str,
    title: str | None,
    uploader: str | None = None,
    details: tuple[int | None, int | None] = (None, None),
) -> str:
    """Build the Markdown caption for a media message.

    Args:
        mtype: Media type keyword (``video``, ``audio`` or ``photo``).
        title: Media title; falls back to ``"Media"``.
        uploader: Uploader/channel name, optional.
        details: Tuple ``(duration, size)`` used for the details line.

    Returns:
        Caption text in Markdown format.
    """
    icon = _MEDIA_ICONS.get(mtype, _FALLBACK_ICON)
    lines = [f"{icon} **{title or 'Media'}**"]
    if uploader:
        lines.append(f"{_UPLOADER_ICON} {uploader}")
    details_line = _details_line(*details)
    if details_line:
        lines.append(details_line)
    return "\n".join(lines)
