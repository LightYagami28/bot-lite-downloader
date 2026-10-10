import asyncio

import pytest

from botlite.downloader import ytdlp


def test_guess_mtype():
    assert ytdlp._guess_mtype("file.mp4") == "video"
    assert ytdlp._guess_mtype("file.MKV") == "video"
    assert ytdlp._guess_mtype("file.mp3") == "audio"
    assert ytdlp._guess_mtype("file.flac") == "audio"
    assert ytdlp._guess_mtype("file.jpg") == "photo"
    assert ytdlp._guess_mtype("file.png") == "photo"
    assert ytdlp._guess_mtype("file.unknown") == "video"


def test_mtype_from_info():
    assert ytdlp._mtype_from_info("pic.jpg", vcodec="h264", acodec="aac") == "photo"
    assert ytdlp._mtype_from_info("vid.mkv", vcodec="h264", acodec="aac") == "video"
    assert ytdlp._mtype_from_info("audio.opus", vcodec="none", acodec="opus") == "audio"
    assert ytdlp._mtype_from_info("track.m4a", vcodec="", acodec="aac") == "audio"
    assert ytdlp._mtype_from_info("track.mp4", vcodec="none", acodec="none") == "video"


def test_logger(monkeypatch):
    logged = []

    def fake_log(lvl, fmt, msg):
        logged.append((lvl, msg))

    monkeypatch.setattr(ytdlp.log, "debug", lambda fmt, msg: fake_log("debug", fmt, msg))
    monkeypatch.setattr(ytdlp.log, "info", lambda fmt, msg: fake_log("info", fmt, msg))
    monkeypatch.setattr(ytdlp.log, "warning", lambda fmt, msg: fake_log("warning", fmt, msg))
    monkeypatch.setattr(ytdlp.log, "error", lambda fmt, msg: fake_log("error", fmt, msg))

    logger = ytdlp._Logger()
    logger.debug("[debug] hidden")
    assert not logged  # message starting with [debug] is skipped
    logger.debug("regular debug")
    assert logged[-1] == ("debug", "regular debug")

    logger.info("info msg")
    assert logged[-1] == ("info", "info msg")

    logger.warning("warn msg")
    assert logged[-1] == ("warning", "warn msg")

    logger.error("err msg")
    assert logged[-1] == ("error", "err msg")


def test_scan_new_files(tmp_path):
    before = set()
    file_vid = tmp_path / "video.mp4"
    file_vid.write_bytes(b"x" * 200)

    file_tiny = tmp_path / "tiny.mp4"
    file_tiny.write_bytes(b"x" * 50)  # <= 100 bytes ignored

    file_txt = tmp_path / "notes.txt"
    file_txt.write_bytes(b"x" * 200)  # non-media ext ignored

    meta = {"title": "Sample"}
    results = ytdlp._scan_new_files(str(tmp_path), before, meta, vcodec="h264", acodec="aac")

    assert len(results) == 1
    path, result_meta, mtype = results[0]
    assert path == str(file_vid)
    assert result_meta["title"] == "Sample"
    assert result_meta["size"] == 200
    assert mtype == "video"


def test_scan_new_files_empty_raises(tmp_path):
    with pytest.raises(RuntimeError, match="yt-dlp finished but no file was written"):
        ytdlp._scan_new_files(str(tmp_path), set(), {}, vcodec="none", acodec="none")


def test_build_opts(tmp_path):
    opts = ytdlp._build_opts(str(tmp_path), None)
    assert opts["noplaylist"] is True
    assert "cookiefile" not in opts

    opts_cookie = ytdlp._build_opts(str(tmp_path), "/path/to/cookies.txt")
    assert opts_cookie["cookiefile"] == "/path/to/cookies.txt"


def test_download_success(tmp_path, monkeypatch):
    async def exercise():
        fake_info = {
            "title": "My Video",
            "uploader": "Uploader",
            "duration": 60,
            "width": 1920,
            "height": 1080,
            "vcodec": "h264",
            "acodec": "aac",
        }

        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, url, download=True):
                # Write an actual file into tmpdir
                out_file = tmp_path / "vid123.mp4"
                out_file.write_bytes(b"x" * 500)
                return fake_info

        monkeypatch.setattr(ytdlp.yt_dlp, "YoutubeDL", FakeYDL)

        results = await ytdlp.download("https://youtube.com/watch?v=vid123", str(tmp_path))
        assert len(results) == 1
        _path, meta, mtype = results[0]
        assert meta["title"] == "My Video"
        assert meta["uploader"] == "Uploader"
        assert mtype == "video"

    asyncio.run(exercise())


def test_download_no_info_raises(tmp_path, monkeypatch):
    async def exercise():
        class FakeYDL:
            def __init__(self, opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def extract_info(self, url, download=True):
                return None

        monkeypatch.setattr(ytdlp.yt_dlp, "YoutubeDL", FakeYDL)

        with pytest.raises(RuntimeError, match="yt-dlp returned no info"):
            await ytdlp.download("https://youtube.com/watch?v=bad", str(tmp_path))

    asyncio.run(exercise())
