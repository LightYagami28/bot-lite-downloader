from botlite.utils.format import build_caption, fmt_dur, fmt_size, fmt_uptime


def test_fmt_size_none_and_units():
    assert fmt_size(None) == "Unknown"
    assert fmt_size(512) == "512.0 B"
    assert fmt_size(1024) == "1.0 KB"


def test_fmt_dur_variants():
    assert fmt_dur(None) == ""
    assert fmt_dur(0) == ""
    assert fmt_dur(59) == "0:59"
    assert fmt_dur(3661) == "1:01:01"


def test_fmt_uptime():
    assert fmt_uptime(3661.8) == "1h 1m 1s"


def test_build_caption_variants():
    caption = build_caption("video", "My Title", "Uploader", 75, 2048)
    assert "🎬 **My Title**" in caption
    assert "👤 Uploader" in caption
    assert "⏱ 1:15" in caption
    assert "📦 2.0 KB" in caption

    fallback = build_caption("unknown", None, None, None, None)
    assert fallback == "📎 **Media**"
