"""Tests for ytdlp audio."""

import pytest
import yt_dlp

from botlite.downloader.ytdlp import _build_audio_opts


def test_audio_options_reject_unknown_or_overlong_duration():
    """Audio options reject unknown or overlong duration."""
    options = _build_audio_opts("voice-dir", None, 1024, 600)
    duration_filter = options["match_filter"]

    assert options["noplaylist"] is True
    assert options["max_filesize"] == 1024
    assert duration_filter({"duration": 600}, incomplete=False) is None
    assert duration_filter({"duration": 601}, incomplete=False)
    assert duration_filter({"duration": None}, incomplete=False)
    assert duration_filter({"duration": None}, incomplete=True) is None


def test_audio_progress_hook_enforces_size_limit():
    """Audio progress hook enforces size limit."""
    options = _build_audio_opts("voice-dir", None, 1024, 600)
    hook = options["progress_hooks"][0]

    hook({"downloaded_bytes": 1024})
    with pytest.raises(yt_dlp.utils.DownloadError, match="voice-chat limit"):
        hook({"downloaded_bytes": 1025})


def test_download_audio_success(tmp_path, monkeypatch):
    """Download audio success."""
    import asyncio

    from botlite.downloader.ytdlp import download_audio

    fake_file = tmp_path / "song.opus"
    fake_file.write_bytes(b"x" * 500)

    class FakeYDL:
        """Fake y d l."""
        def __init__(self, opts):
            """Init."""
            self.opts = opts

        def __enter__(self):
            """Enter."""
            return self

        def __exit__(self, *args):
            """Exit."""

        def extract_info(self, url, download=True):
            """Extract info."""
            return {"title": "Cool Song", "duration": 180}

        def prepare_filename(self, info):
            """Prepare filename."""
            return str(fake_file)

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

    async def exercise():
        """Exercise."""
        path, meta = await download_audio(
            "https://soundcloud.com/song",
            str(tmp_path),
            max_file_size=1000,
            max_duration=300,
        )
        assert path == str(fake_file)
        assert meta["title"] == "Cool Song"
        assert meta["duration"] == 180
        assert meta["size"] == 500

    asyncio.run(exercise())


def test_download_audio_no_info_raises(tmp_path, monkeypatch):
    """Download audio no info raises."""
    import asyncio

    from botlite.downloader.ytdlp import download_audio

    class FakeYDL:
        """Fake y d l."""
        def __init__(self, opts):
            """Init."""

        def __enter__(self):
            """Enter."""
            return self

        def __exit__(self, *args):
            """Exit."""

        def extract_info(self, url, download=True):
            """Extract info."""
            return

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)

    async def exercise():
        """Exercise."""
        with pytest.raises(RuntimeError, match="yt-dlp returned no audio information"):
            await download_audio(
                "https://soundcloud.com/song",
                str(tmp_path),
                max_file_size=1000,
                max_duration=300,
            )

    asyncio.run(exercise())
