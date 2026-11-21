"""Tests for gallery."""

import asyncio
from pathlib import Path

from botlite.downloader import gallery


class FakeProcess:
    """Fake process."""

    def __init__(self, returncode=0, stderr=b"", block=False):
        """Init."""
        self.returncode = returncode
        self.stderr = stderr
        self.block = block
        self.killed = False

    async def communicate(self):
        """Communicate."""
        if self.block and not self.killed:
            await asyncio.Event().wait()
        return b"", self.stderr

    def kill(self):
        """Kill."""
        self.killed = True


def test_gallery_download_uses_exec_args_and_keeps_partial_results(monkeypatch, tmp_path):
    """Gallery download uses exec args and keeps partial results."""

    async def exercise():
        """Exercise."""
        captured = {}

        async def create_process(*args, **kwargs):
            """Create process."""
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
    """Gallery download kills process on timeout."""

    async def exercise():
        """Exercise."""
        process = FakeProcess(block=True)

        async def create_process(*_args, **_kwargs):
            """Create process."""
            return process

        async def timeout_immediately(awaitable, timeout):
            """Timeout immediately."""
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
    """Gallery download rejects non http url before launch."""

    async def exercise():
        """Exercise."""
        try:
            await gallery.download("file:///etc/passwd", str(tmp_path))
        except ValueError as exc:
            assert "HTTP(S)" in str(exc)
        else:
            raise AssertionError("non-HTTP URL was accepted")

    asyncio.run(exercise())


def test_gallery_uses_static_program_prefix_and_validated_args(monkeypatch, tmp_path):
    """Gallery uses a literal program prefix and validated argv elements."""
    captured = {}

    async def create_process(*args, **kwargs):
        """Capture the spawn call without starting a process."""
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(gallery.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(gallery, "_scan_files", lambda _dir: [])
    asyncio.run(gallery.download("https://example.test/gallery", str(tmp_path)))

    assert captured["args"][0] == gallery.sys.executable
    assert captured["args"][1:3] == ("-m", "gallery_dl")
    assert captured["args"][3] == "--directory"
    assert captured["args"][4] == str(tmp_path)
    assert captured["args"][-1] == "https://example.test/gallery"


def test_gallery_rejects_control_characters_and_option_like_values(tmp_path):
    """Gallery refuses URLs and argv values containing control characters."""
    try:
        gallery._command("https://example.test/gallery\n--cookies evil", str(tmp_path))
    except ValueError as exc:
        assert "URL" in str(exc)
    else:
        raise AssertionError("URL with control characters was accepted")

    try:
        gallery._validated_arg("--cookies", "cookie file")
    except ValueError as exc:
        assert "cookie file" in str(exc)
    else:
        raise AssertionError("option-like argv value was accepted")


def test_gallery_rejects_commands_outside_the_allowlist():
    """Gallery only allows the gallery_dl module to be executed."""
    try:
        gallery._allow_command("os")
    except ValueError as exc:
        assert "not allowed" in str(exc)
    else:
        raise AssertionError("command outside the allowlist was accepted")
