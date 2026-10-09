import pytest
import yt_dlp

from botlite.downloader.ytdlp import _build_audio_opts


def test_audio_options_reject_unknown_or_overlong_duration():
    options = _build_audio_opts("/tmp/voice", None, 1024, 600)
    duration_filter = options["match_filter"]

    assert options["noplaylist"] is True
    assert options["max_filesize"] == 1024
    assert duration_filter({"duration": 600}, incomplete=False) is None
    assert duration_filter({"duration": 601}, incomplete=False)
    assert duration_filter({"duration": None}, incomplete=False)
    assert duration_filter({"duration": None}, incomplete=True) is None


def test_audio_progress_hook_enforces_size_limit():
    options = _build_audio_opts("/tmp/voice", None, 1024, 600)
    hook = options["progress_hooks"][0]

    hook({"downloaded_bytes": 1024})
    with pytest.raises(yt_dlp.utils.DownloadError, match="voice-chat limit"):
        hook({"downloaded_bytes": 1025})
