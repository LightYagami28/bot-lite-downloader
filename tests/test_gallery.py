import asyncio
from pathlib import Path

from botlite.downloader import gallery


class FakeProcess:
    def __init__(self, returncode=0, stderr=b"", block=False):
        self.returncode = returncode
        self.stderr = stderr
        self.block = block
        self.killed = False

    async def communicate(self):
        if self.block and not self.killed:
            await asyncio.Event().wait()
        return b"", self.stderr

    def kill(self):
        self.killed = True


def test_gallery_download_uses_exec_args_and_keeps_partial_results(monkeypatch, tmp_path):
    async def exercise():
        captured = {}

        async def create_process(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            directory = Path(args[args.index("--directory") + 1])
            (directory / "image.jpg").write_bytes(b"x" * 120)
            return FakeProcess(returncode=1)

        monkeypatch.setattr(gallery.asyncio, "create_subprocess_exec", create_process)
        results = await gallery.download("https://example.test/gallery", str(tmp_path))

        assert captured["args"][-1] == "https://example.test/gallery"
        assert "shell" not in captured["kwargs"]
        assert results[0][2] == "photo"

    asyncio.run(exercise())


def test_gallery_download_kills_process_on_timeout(monkeypatch, tmp_path):
    async def exercise():
        process = FakeProcess(block=True)

        async def create_process(*_args, **_kwargs):
            return process

        async def timeout_immediately(awaitable, timeout):
            awaitable.close()
            raise TimeoutError

        monkeypatch.setattr(gallery.asyncio, "create_subprocess_exec", create_process)
        monkeypatch.setattr(gallery.asyncio, "wait_for", timeout_immediately)

        try:
            await gallery.download("https://example.test/gallery", str(tmp_path))
        except TimeoutError as exc:
            assert "120-second" in str(exc)
        else:
            raise AssertionError("timed-out gallery download was not rejected")
        assert process.killed

    asyncio.run(exercise())


def test_gallery_download_rejects_non_http_url_before_launch(tmp_path):
    async def exercise():
        try:
            await gallery.download("file:///etc/passwd", str(tmp_path))
        except ValueError as exc:
            assert "HTTP(S)" in str(exc)
        else:
            raise AssertionError("non-HTTP URL was accepted")

    asyncio.run(exercise())
