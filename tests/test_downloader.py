import asyncio
import os
import shutil
import tempfile

import pytest

from botlite.downloader import download


def test_download_ytdlp_success(monkeypatch):
    async def exercise():
        mock_results = [("/fake/path/vid.mp4", {"title": "Test Video"}, "video")]

        async def mock_ytdlp(url, outdir):
            assert "yt" in outdir
            return mock_results

        monkeypatch.setattr("botlite.downloader.ytdlp.download", mock_ytdlp)

        tmpdir, results = await download("https://youtube.com/watch?v=123")
        assert results == mock_results
        assert os.path.isdir(tmpdir)
        shutil.rmtree(tmpdir)

    asyncio.run(exercise())


def test_download_ytdlp_fails_gallery_succeeds(monkeypatch):
    async def exercise():
        mock_results = [("/fake/path/pic.jpg", {"title": "Photo"}, "photo")]

        async def mock_ytdlp(url, outdir):
            raise RuntimeError("yt-dlp unsupported URL")

        async def mock_gallery(url, outdir):
            assert "gd" in outdir
            return mock_results

        monkeypatch.setattr("botlite.downloader.ytdlp.download", mock_ytdlp)
        monkeypatch.setattr("botlite.downloader.gallery.download", mock_gallery)

        tmpdir, results = await download("https://instagram.com/p/123")
        assert results == mock_results
        assert os.path.isdir(tmpdir)
        shutil.rmtree(tmpdir)

    asyncio.run(exercise())


def test_download_both_fail_cleans_up_tmpdir(monkeypatch):
    async def exercise():
        async def mock_ytdlp(url, outdir):
            raise RuntimeError("yt-dlp failure")

        async def mock_gallery(url, outdir):
            return []

        monkeypatch.setattr("botlite.downloader.ytdlp.download", mock_ytdlp)
        monkeypatch.setattr("botlite.downloader.gallery.download", mock_gallery)

        created_dirs = []
        orig_mkdtemp = tempfile.mkdtemp

        def tracked_mkdtemp(*args, **kwargs):
            d = orig_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        monkeypatch.setattr("tempfile.mkdtemp", tracked_mkdtemp)

        with pytest.raises(RuntimeError, match="Both yt-dlp and gallery-dl could not extract"):
            await download("https://example.com/not-media")

        assert len(created_dirs) == 1
        assert not os.path.exists(created_dirs[0])

    asyncio.run(exercise())
