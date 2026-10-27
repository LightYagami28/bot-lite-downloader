"""Tests for the branches that the module-level suites do not reach (error paths, edge cases)."""

import asyncio
import hashlib
import hmac
import importlib
import logging
import signal
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from pytgcalls.exceptions import NotInCallError
from pytgcalls.types import StreamEnded
from pytgcalls.types.stream.device import Device

from botlite import app, config, voice
from botlite import webapp as webapp_pkg
from botlite.downloader import download, gallery, ytdlp
from botlite.handlers import commands, url
from botlite.utils import system
from botlite.voice import VoiceChatManager
from botlite.webapp import auth, server

# ── config ────────────────────────────────────────────────────────────────────


def test_config_loads_without_dotenv():
    saved = sys.modules.get("dotenv")
    sys.modules["dotenv"] = None  # makes "from dotenv import ..." raise ImportError
    try:
        importlib.reload(config)
    finally:
        if saved is None:
            sys.modules.pop("dotenv", None)
        else:
            sys.modules["dotenv"] = saved
        importlib.reload(config)


# ── downloader package ────────────────────────────────────────────────────────


def test_download_reports_error_when_gallery_dl_raises(monkeypatch):
    async def no_results(_url, _outdir):
        return []

    async def gallery_boom(_url, _outdir):
        raise RuntimeError("gallery-dl broke")

    monkeypatch.setattr("botlite.downloader.ytdlp.download", no_results)
    monkeypatch.setattr("botlite.downloader.gallery.download", gallery_boom)

    with pytest.raises(RuntimeError, match="Both yt-dlp and gallery-dl"):
        asyncio.run(download("https://example.test/video"))


# ── gallery-dl engine ─────────────────────────────────────────────────────────


class FakeProcess:
    def __init__(self, returncode=0, stderr=b"", kill_error=None, block=False):
        self.returncode = returncode
        self._stderr = stderr
        self._kill_error = kill_error
        self._block = block
        self.killed = False

    async def communicate(self):
        if self._block and not self.killed:
            await asyncio.sleep(3600)
        return b"", self._stderr

    def kill(self):
        self.killed = True
        if self._kill_error:
            raise self._kill_error


def test_gallery_scan_files_classifies_and_skips(tmp_path):
    (tmp_path / "tiny.mp4").write_bytes(b"x" * 10)
    (tmp_path / "folder").mkdir()
    (tmp_path / "a.mp4").write_bytes(b"x" * 200)
    (tmp_path / "b.jpg").write_bytes(b"x" * 200)
    (tmp_path / "c.mp3").write_bytes(b"x" * 200)
    (tmp_path / "d.txt").write_bytes(b"x" * 200)

    results = gallery._scan_files(str(tmp_path))

    assert [(Path(fp).name, mtype) for fp, _, mtype in results] == [
        ("a.mp4", "video"),
        ("b.jpg", "photo"),
        ("c.mp3", "audio"),
    ]


def test_gallery_scan_files_without_usable_files_fails(tmp_path):
    (tmp_path / "d.txt").write_bytes(b"x" * 200)
    with pytest.raises(RuntimeError, match="no usable files"):
        gallery._scan_files(str(tmp_path))


def test_gallery_download_passes_cookie_file(monkeypatch, tmp_path):
    seen = {}

    async def create_process(*args, **_kwargs):
        seen["command"] = args
        return FakeProcess()

    monkeypatch.setattr(gallery.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(gallery, "resolve_cookie", lambda _url: "cookies.txt")
    monkeypatch.setattr(gallery, "_scan_files", lambda _dir: [("f.jpg", {}, "photo")])

    results = asyncio.run(gallery.download("https://example.test/gallery", str(tmp_path)))

    assert results == [("f.jpg", {}, "photo")]
    assert "--cookies" in seen["command"]
    assert "cookies.txt" in seen["command"]


def test_gallery_download_survives_a_process_that_already_exited(monkeypatch, tmp_path):
    process = FakeProcess(block=True, kill_error=ProcessLookupError())

    async def create_process(*_args, **_kwargs):
        return process

    async def timeout_immediately(awaitable, timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(gallery.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(gallery.asyncio, "wait_for", timeout_immediately)

    with pytest.raises(TimeoutError, match="120-second"):
        asyncio.run(gallery.download("https://example.test/gallery", str(tmp_path)))
    assert process.killed


def test_gallery_download_rejects_failing_exit_code(monkeypatch, tmp_path):
    async def create_process(*_args, **_kwargs):
        return FakeProcess(returncode=2, stderr=b"boom")

    monkeypatch.setattr(gallery.asyncio, "create_subprocess_exec", create_process)

    with pytest.raises(RuntimeError, match="gallery-dl exited 2: boom"):
        asyncio.run(gallery.download("https://example.test/gallery", str(tmp_path)))


# ── yt-dlp audio engine ───────────────────────────────────────────────────────


class FakeYoutubeDL:
    info: dict | None = None
    filename = ""

    def __init__(self, _opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def extract_info(self, _url, download=True):
        return type(self).info

    def prepare_filename(self, _info):
        return type(self).filename


def _download_audio(tmp_path, *, max_file_size=100):
    return asyncio.run(
        ytdlp.download_audio(
            "https://example.test/a", str(tmp_path), max_file_size=max_file_size, max_duration=60
        )
    )


@pytest.fixture
def fake_ydl(monkeypatch, tmp_path):
    monkeypatch.setattr(ytdlp.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    monkeypatch.setattr(ytdlp, "resolve_cookie", lambda _url: None)
    FakeYoutubeDL.info = {"title": "Song", "duration": 5}
    FakeYoutubeDL.filename = str(tmp_path / "missing.m4a")
    return FakeYoutubeDL


def test_audio_options_include_cookie_file(tmp_path):
    opts = ytdlp._build_audio_opts(str(tmp_path), "cookies.txt", 10, 10)
    assert opts["cookiefile"] == "cookies.txt"


def test_download_audio_without_info_fails(fake_ydl, tmp_path):
    fake_ydl.info = None
    with pytest.raises(RuntimeError, match="no audio information"):
        _download_audio(tmp_path)


def test_download_audio_recovers_the_single_downloaded_file(fake_ydl, tmp_path):
    produced = tmp_path / "real.m4a"
    produced.write_bytes(b"audio")

    path, meta = _download_audio(tmp_path)

    assert path == str(produced)
    assert meta == {"title": "Song", "duration": 5, "size": 5}


def test_download_audio_rejects_ambiguous_output(fake_ydl, tmp_path):
    (tmp_path / "one.m4a").write_bytes(b"a")
    (tmp_path / "two.m4a").write_bytes(b"a")
    with pytest.raises(RuntimeError, match="unambiguous"):
        _download_audio(tmp_path)


def test_download_audio_rejects_oversized_file(fake_ydl, tmp_path):
    produced = tmp_path / "big.m4a"
    produced.write_bytes(b"x" * 50)
    fake_ydl.filename = str(produced)
    with pytest.raises(ValueError, match="size limit"):
        _download_audio(tmp_path, max_file_size=10)


def test_download_audio_rejects_empty_file(fake_ydl, tmp_path):
    produced = tmp_path / "empty.m4a"
    produced.write_bytes(b"")
    fake_ydl.filename = str(produced)
    with pytest.raises(RuntimeError, match="empty audio file"):
        _download_audio(tmp_path)


# ── system utilities ──────────────────────────────────────────────────────────


def test_cleanup_old_temps_logs_when_the_directory_cannot_be_inspected(monkeypatch, tmp_path):
    (tmp_path / "botlite_stale").mkdir()
    monkeypatch.setattr(system.tempfile, "gettempdir", lambda: str(tmp_path))

    def unreadable(_path):
        raise OSError("denied")

    monkeypatch.setattr(system.os.path, "getmtime", unreadable)

    system.cleanup_old_temps()

    assert (tmp_path / "botlite_stale").exists()


def _install_signal_handlers(monkeypatch):
    handlers = {}
    monkeypatch.setattr(
        system.signal, "signal", lambda sig, handler: handlers.update({sig: handler})
    )
    return handlers


def test_setup_signals_reports_a_failing_disconnect(monkeypatch, caplog):
    handlers = _install_signal_handlers(monkeypatch)

    async def exercise():
        async def disconnect():
            raise RuntimeError("disconnect failed")

        system.setup_signals(disconnect)
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        await asyncio.sleep(0.05)

    with caplog.at_level(logging.ERROR, logger="botlite.system"):
        asyncio.run(exercise())
    assert any("shutdown failed" in record.getMessage() for record in caplog.records)


def test_setup_signals_reports_a_cancelled_disconnect(monkeypatch, caplog):
    handlers = _install_signal_handlers(monkeypatch)

    async def exercise():
        async def disconnect():
            raise asyncio.CancelledError

        system.setup_signals(disconnect)
        handlers[signal.SIGINT](signal.SIGINT, None)
        await asyncio.sleep(0.05)

    with caplog.at_level(logging.WARNING, logger="botlite.system"):
        asyncio.run(exercise())
    assert any("cancelled" in record.getMessage() for record in caplog.records)


def test_setup_signals_tolerates_unregistrable_signals(monkeypatch, caplog):
    def refuse(_sig, _handler):
        raise ValueError("not in main thread")

    monkeypatch.setattr(system.signal, "signal", refuse)

    async def exercise():
        system.setup_signals(AsyncMock())

    with caplog.at_level(logging.WARNING, logger="botlite.system"):
        asyncio.run(exercise())
    assert any("Unable to register handler" in record.getMessage() for record in caplog.records)


# ── bootstrap ─────────────────────────────────────────────────────────────────


def test_setup_logging_configures_handlers_when_none_exist(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logging.root, "handlers", [])
    captured = {}
    monkeypatch.setattr(app.logging, "basicConfig", lambda **kwargs: captured.update(kwargs))

    app.setup_logging()

    assert len(captured["handlers"]) == 2
    for handler in captured["handlers"]:
        handler.close()


def test_run_starts_the_event_loop(monkeypatch):
    called = []

    async def fake_main():
        called.append(True)

    monkeypatch.setattr(app, "_main", fake_main)
    app.run()
    assert called == [True]


def test_disconnect_callback_shuts_voice_down_and_cleans_up(monkeypatch):
    captured = {}
    actions = []

    async def exercise():
        monkeypatch.setattr(app.config, "validate", lambda: None)
        monkeypatch.setattr(app, "setup_signals", lambda fn: captured.update(disconnect=fn))
        monkeypatch.setattr(app, "cleanup_old_temps", lambda: None)
        monkeypatch.setattr(app.db, "init", lambda: None)
        monkeypatch.setattr(app, "WEBAPP_PUBLIC_URL", "")
        monkeypatch.setattr(app, "VOICE_ENABLED", True)

        client = MagicMock()
        client.start = AsyncMock()
        client.run_until_disconnected = AsyncMock()
        client.disconnect = AsyncMock(side_effect=lambda: actions.append("client.disconnect"))
        monkeypatch.setattr(app, "client", client)

        manager = MagicMock()
        manager.start = AsyncMock()
        manager.shutdown = AsyncMock(side_effect=lambda: actions.append("voice.shutdown"))
        manager.cleanup_after_disconnect = MagicMock(
            side_effect=lambda: actions.append("voice.cleanup")
        )
        monkeypatch.setattr(app, "initialize_voice", lambda: manager)
        monkeypatch.setattr(app, "get_voice_manager", lambda: manager)

        await app._main()
        actions.clear()
        await captured["disconnect"]()

    asyncio.run(exercise())

    assert actions == ["voice.shutdown", "client.disconnect", "voice.cleanup"]


# ── commands ──────────────────────────────────────────────────────────────────


class StatusMessage:
    def __init__(self):
        self.edits = []

    async def edit(self, text, **kwargs):
        self.edits.append((text, kwargs))


class CommandEvent:
    def __init__(
        self,
        *,
        chat_id=-100,
        sender_id=100,
        is_private=True,
        is_group=False,
        text="",
        match=None,
        reply_error=None,
    ):
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.is_private = is_private
        self.is_group = is_group
        self.raw_text = text
        self.pattern_match = match
        self.replies = []
        self.status = StatusMessage()
        self._reply_error = reply_error

    async def reply(self, text, **kwargs):
        if self._reply_error is not None:
            raise self._reply_error
        self.replies.append((text, kwargs))
        return self.status


def test_dashboard_button_falls_back_to_a_url_button(monkeypatch):
    import telethon.tl.types as tl_types

    monkeypatch.setattr(commands, "WEBAPP_PUBLIC_URL", "https://example.test/app")
    monkeypatch.delattr(tl_types, "KeyboardInlineButton")
    monkeypatch.setattr(commands.Button, "url", staticmethod(lambda text, url: (text, url)))

    assert commands._dashboard_button() == [[("📊 Open Dashboard", "https://example.test/app")]]


@pytest.mark.parametrize("handler", ["cmd_start", "cmd_help", "cmd_status"])
def test_public_commands_ignore_disallowed_chats(monkeypatch, handler):
    monkeypatch.setattr(commands, "_group_allowed", lambda _event: False)
    event = CommandEvent()
    asyncio.run(getattr(commands, handler)(event))
    assert event.replies == []


@pytest.mark.parametrize("handler", ["cmd_ban", "cmd_unban"])
def test_ban_commands_ignore_non_sudo_users(monkeypatch, handler):
    monkeypatch.setattr(commands, "SUDO_USERS", [1])
    event = CommandEvent(sender_id=999)
    asyncio.run(getattr(commands, handler)(event))
    assert event.replies == []


def _enable_voice(monkeypatch):
    monkeypatch.setattr(commands, "VOICE_ENABLED", True)
    monkeypatch.setattr(commands, "_group_allowed", lambda _event: True)
    monkeypatch.setattr(commands.db, "is_banned", lambda _uid: False)
    monkeypatch.setattr(commands, "check_cooldown", lambda _cooldowns, _uid: 0.0)
    commands.active_downloads.discard(100)


def _play_event(**kwargs):
    return CommandEvent(
        is_private=False, is_group=True, text="/play https://example.test/a", **kwargs
    )


def test_voice_play_respects_the_cooldown(monkeypatch):
    _enable_voice(monkeypatch)
    monkeypatch.setattr(commands, "check_cooldown", lambda _cooldowns, _uid: 7.0)
    event = _play_event()

    asyncio.run(commands.cmd_voice_play(event))

    assert "Please wait" in event.replies[0][0]


def test_voice_play_reports_a_download_failure_and_cleans_up(monkeypatch):
    _enable_voice(monkeypatch)
    cleaned = []

    class TrackedDirectory:
        name = tempfile.gettempdir()

        def cleanup(self):
            cleaned.append(True)

    async def failing_download(*_args, **_kwargs):
        raise ValueError("<too long>")

    monkeypatch.setattr(commands.tempfile, "TemporaryDirectory", lambda **_kw: TrackedDirectory())
    monkeypatch.setattr(commands, "download_audio", failing_download)
    event = _play_event()

    asyncio.run(commands.cmd_voice_play(event))

    assert cleaned == [True]
    text, kwargs = event.status.edits[0]
    assert "Could not start voice playback" in text
    assert "&lt;too long&gt;" in text
    assert kwargs["parse_mode"] == "html"
    assert 100 not in commands.active_downloads


def test_voice_play_logs_when_the_status_message_cannot_be_sent(monkeypatch, caplog):
    _enable_voice(monkeypatch)
    event = _play_event(reply_error=RuntimeError("telegram down"))
    # The first reply (the one that creates the status message) must fail.
    event.replies.append(("seed", {}))

    with caplog.at_level(logging.ERROR, logger="botlite.commands"):
        asyncio.run(commands.cmd_voice_play(event))

    assert any("Unable to prepare voice playback status" in r.getMessage() for r in caplog.records)


def test_voice_controls_are_ignored_when_voice_is_disabled(monkeypatch):
    monkeypatch.setattr(commands, "VOICE_ENABLED", False)
    event = _play_event()
    asyncio.run(commands.cmd_voice_control(event))
    assert event.replies == []


# ── URL handler ───────────────────────────────────────────────────────────────


class UrlMessage:
    def __init__(self, text):
        self.text = text
        self.caption = None
        self.id = 1


class UrlStatus:
    def __init__(self, delete_error=None):
        self.edits = []
        self.deleted = False
        self._delete_error = delete_error

    async def edit(self, text, **kwargs):
        self.edits.append(text)

    async def delete(self):
        if self._delete_error is not None:
            raise self._delete_error
        self.deleted = True


class UrlEvent:
    def __init__(self, text="https://example.test/v", status=None):
        self.chat_id = 1
        self.sender_id = 4242
        self.is_private = True
        self.is_group = False
        self.message = UrlMessage(text)
        self.replies = []
        self.status = status or UrlStatus()

    async def reply(self, text, **kwargs):
        self.replies.append(text)
        return self.status


def test_send_media_attaches_audio_attributes(monkeypatch, tmp_path):
    fp = tmp_path / "song.mp3"
    fp.write_bytes(b"x" * 200)
    send_file = AsyncMock()
    monkeypatch.setattr(url.client, "send_file", send_file)

    asyncio.run(url._send_media(UrlEvent(), str(fp), {"duration": 3, "title": "Song"}, "audio"))

    attributes = send_file.await_args.kwargs["attributes"]
    assert attributes[0].title == "Song"


def test_upload_results_reports_a_failed_send(monkeypatch, tmp_path):
    fp = tmp_path / "clip.mp4"
    fp.write_bytes(b"x" * 200)
    event = UrlEvent()

    async def broken_send(*_args, **_kwargs):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(url, "_send_media", broken_send)

    sent = asyncio.run(url._upload_results(event, event.status, [(str(fp), {}, "video")]))

    assert sent == 0
    assert "Failed to send file 1" in event.replies[0]
    assert not fp.exists()


def test_upload_results_tolerates_a_file_that_cannot_be_removed(monkeypatch, tmp_path):
    fp = tmp_path / "clip.mp4"
    fp.write_bytes(b"x" * 200)
    event = UrlEvent()

    def refuse(_path):
        raise OSError("busy")

    monkeypatch.setattr(url, "_send_media", AsyncMock())
    monkeypatch.setattr(url.os, "remove", refuse)

    sent = asyncio.run(url._upload_results(event, event.status, [(str(fp), {}, "video")]))

    assert sent == 1


def test_url_handler_ignores_disallowed_chats(monkeypatch):
    monkeypatch.setattr(url, "_group_allowed", lambda _event: False)
    event = UrlEvent()
    asyncio.run(url.url_handler(event))
    assert event.replies == []


def test_url_handler_stops_when_a_guard_rejects(monkeypatch):
    monkeypatch.setattr(url, "_group_allowed", lambda _event: True)
    monkeypatch.setattr(url, "_check_guards", AsyncMock(return_value=True))
    event = UrlEvent()
    asyncio.run(url.url_handler(event))
    assert event.replies == []


def _handler_setup(monkeypatch, tmp_path, *, results, uploaded=1, status=None):
    monkeypatch.setattr(url, "_group_allowed", lambda _event: True)
    monkeypatch.setattr(url, "_check_guards", AsyncMock(return_value=False))
    counters = []
    monkeypatch.setattr(url.db, "increment", counters.append)

    async def fake_download(_url):
        return str(tmp_path), results

    monkeypatch.setattr(url, "download", fake_download)
    monkeypatch.setattr(url, "_upload_results", AsyncMock(return_value=uploaded))
    return UrlEvent(status=status), counters


def test_url_handler_reports_missing_media(monkeypatch, tmp_path):
    event, counters = _handler_setup(monkeypatch, tmp_path, results=[])
    asyncio.run(url.url_handler(event))
    assert "No media found" in event.status.edits[0]
    assert counters == ["failed_downloads"]


def test_url_handler_ignores_a_status_message_that_cannot_be_deleted(monkeypatch, tmp_path):
    status = UrlStatus(delete_error=RuntimeError("gone"))
    event, counters = _handler_setup(
        monkeypatch, tmp_path, results=[("f", {}, "video")], status=status
    )
    asyncio.run(url.url_handler(event))
    assert counters == ["total_downloads"]


def test_url_handler_reports_when_nothing_could_be_sent(monkeypatch, tmp_path):
    event, counters = _handler_setup(
        monkeypatch, tmp_path, results=[("f", {}, "video")], uploaded=0
    )
    asyncio.run(url.url_handler(event))
    assert "Could not send any files" in event.status.edits[-1]
    assert counters == ["failed_downloads"]


# ── voice-chat manager ────────────────────────────────────────────────────────


class Calls:
    def __init__(self, leave_error=None):
        self.start_count = 0
        self.leave_error = leave_error

    def on_update(self):
        return lambda callback: callback

    async def start(self):
        self.start_count += 1

    async def play(self, chat_id, path, *, config):
        pass

    async def leave_call(self, chat_id):
        if self.leave_error is not None:
            raise self.leave_error

    async def pause(self, chat_id):
        return True

    async def resume(self, chat_id):
        return True


def _directory():
    directory = tempfile.TemporaryDirectory()
    return directory, Path(directory.name) / "a.ogg"


def test_voice_start_is_idempotent():
    async def exercise():
        calls = Calls()
        manager = VoiceChatManager(calls)
        await manager.start()
        await manager.start()
        assert calls.start_count == 1

    asyncio.run(exercise())


def test_voice_play_requires_a_started_manager():
    async def exercise():
        directory, path = _directory()
        with pytest.raises(RuntimeError, match="not running"):
            await VoiceChatManager(Calls()).play(1, str(path), "T", directory)
        directory.cleanup()

    asyncio.run(exercise())


def test_voice_play_rechecks_the_state_after_waiting_for_the_lock():
    async def exercise():
        manager = VoiceChatManager(Calls())
        await manager.start()
        directory, path = _directory()
        async with manager._lock_for(1):
            task = asyncio.create_task(manager.play(1, str(path), "T", directory))
            await asyncio.sleep(0)
            manager._closed = True
        with pytest.raises(RuntimeError, match="not running"):
            await task
        directory.cleanup()

    asyncio.run(exercise())


def test_voice_pause_and_resume_need_an_active_session():
    async def exercise():
        manager = VoiceChatManager(Calls())
        await manager.start()
        assert await manager.pause(1) is False
        assert await manager.resume(1) is False

        directory, path = _directory()
        await manager.play(1, str(path), "T", directory)
        assert await manager.pause(1) is True
        assert await manager.resume(1) is True
        await manager.stop(1)

    asyncio.run(exercise())


def test_voice_shutdown_is_idempotent_and_survives_leave_failures():
    async def exercise():
        calls = Calls()
        manager = VoiceChatManager(calls)
        await manager.start()
        manager._lock_for(99)  # a lock without a session is skipped
        directory, path = _directory()
        await manager.play(1, str(path), "T", directory)
        calls.leave_error = RuntimeError("network")

        await manager.shutdown()
        await manager.shutdown()

    asyncio.run(exercise())


def test_voice_cleanup_after_disconnect_removes_pending_files():
    async def exercise():
        manager = VoiceChatManager(Calls())
        await manager.start()
        directory, path = _directory()
        path.write_bytes(b"a")
        await manager.play(1, str(path), "T", directory)

        manager.cleanup_after_disconnect()

        assert not path.exists()
        assert manager._sessions == {}

    asyncio.run(exercise())


def test_voice_stop_tolerates_a_call_that_already_ended():
    async def exercise():
        manager = VoiceChatManager(Calls(leave_error=NotInCallError()))
        await manager.start()
        directory, path = _directory()
        await manager.play(1, str(path), "T", directory)
        assert await manager.stop(1) is True

    asyncio.run(exercise())


def test_voice_updates_only_react_to_ended_streams_of_active_chats():
    async def exercise():
        calls = Calls()
        manager = VoiceChatManager(calls)
        await manager.start()
        ended = StreamEnded(7, StreamEnded.Type.AUDIO, Device.MICROPHONE)

        await manager._on_update(None, object())  # not a StreamEnded
        await manager._on_update(None, ended)  # chat without a session

        directory, path = _directory()
        await manager.play(7, str(path), "T", directory)
        calls.leave_error = RuntimeError("network")
        await manager._on_update(None, ended)  # cleanup failure is logged, not raised

    asyncio.run(exercise())


def test_get_voice_manager_returns_the_initialised_manager(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(voice, "_voice_manager", sentinel)
    assert voice.get_voice_manager() is sentinel


def test_get_voice_manager_requires_initialisation(monkeypatch):
    monkeypatch.setattr(voice, "_voice_manager", None)
    with pytest.raises(RuntimeError, match="disabled or not initialized"):
        voice.get_voice_manager()


# ── web application ───────────────────────────────────────────────────────────


def test_start_webapp_cleans_up_when_the_server_cannot_start(monkeypatch):
    cleaned = []

    class FailingRunner:
        def __init__(self, *_args, **_kwargs):
            pass

        async def setup(self):
            raise RuntimeError("port busy")

        async def cleanup(self):
            cleaned.append(True)

    monkeypatch.setattr(webapp_pkg, "_runner", None)
    monkeypatch.setattr(webapp_pkg.web, "AppRunner", FailingRunner)

    with pytest.raises(RuntimeError, match="port busy"):
        asyncio.run(webapp_pkg.start_webapp())
    assert cleaned == [True]
    assert webapp_pkg._runner is None


TOKEN = "123456:TEST-TOKEN"


def _signed(params):
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode({**params, "hash": digest})


@pytest.fixture
def bot_token(monkeypatch):
    monkeypatch.setattr(auth, "BOT_TOKEN", TOKEN)


def test_init_data_with_a_malformed_query_string_is_rejected(bot_token):
    assert auth.validate_init_data("not-a-query-string") is None


def test_init_data_without_any_field_is_rejected(bot_token, monkeypatch):
    monkeypatch.setattr(auth.urllib.parse, "parse_qsl", lambda *_a, **_k: [])
    assert auth.validate_init_data("x=1") is None


@pytest.mark.parametrize("params", [{"user": "{}"}, {"auth_date": "yesterday", "user": "{}"}])
def test_init_data_with_a_missing_or_invalid_auth_date_is_rejected(bot_token, params):
    assert auth.validate_init_data(_signed(params)) is None


def test_init_data_with_a_valid_signature_is_accepted(bot_token):
    user = auth.validate_init_data(
        _signed({"auth_date": str(int(time.time())), "user": '{"id": 5}'})
    )
    assert user == {"id": 5}


def test_unhandled_handler_errors_become_500_with_security_headers(monkeypatch):
    async def broken(_request):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "api_status", broken)

    async def exercise():
        async with TestClient(TestServer(server.create_app())) as client:
            response = await client.get("/api/status")
            return response.status, dict(response.headers)

    status, headers = asyncio.run(exercise())

    assert status == 500
    assert headers["X-Content-Type-Options"] == "nosniff"
