"""Tests for voice."""

import asyncio
import tempfile
from pathlib import Path

from botlite import voice
from botlite.voice import Playback, VoiceChatManager


class FakeCalls:
    """Fake calls."""

    def __init__(self):
        """Init."""
        self.started = False
        self.played = []
        self.left = []

    def on_update(self):
        """On update."""
        return lambda callback: callback

    async def start(self):
        """Start."""
        self.started = True

    async def play(self, chat_id, path, *, config):
        """Play."""
        self.played.append((chat_id, path, config.auto_start))

    async def leave_call(self, chat_id):
        """Leave call."""
        self.left.append(chat_id)

    async def pause(self, chat_id):
        """Pause."""
        return True

    async def resume(self, chat_id):
        """Resume."""
        return True


def test_voice_manager_keeps_audio_until_stop_then_removes_it():
    """Voice manager keeps audio until stop then removes it."""

    async def exercise():
        """Exercise."""
        calls = FakeCalls()
        manager = VoiceChatManager(calls)
        await manager.start()
        first = tempfile.TemporaryDirectory()
        first_file = Path(first.name) / "first.ogg"
        first_file.write_bytes(b"audio")

        await manager.play(-100123, str(first_file), Playback(first, "First"))
        assert first_file.exists()
        assert calls.played == [(-100123, str(first_file), False)]

        second = tempfile.TemporaryDirectory()
        second_file = Path(second.name) / "second.ogg"
        second_file.write_bytes(b"audio")
        await manager.play(-100123, str(second_file), Playback(second, "Second"))
        assert not first_file.exists()
        assert calls.left == [-100123]
        assert await manager.stop(-100123)
        assert not second_file.exists()
        assert calls.left == [-100123, -100123]
        assert not await manager.stop(-100123)

    asyncio.run(exercise())


def test_stream_end_leaves_call_and_releases_audio():
    """Stream end leaves call and releases audio."""

    async def exercise():
        """Exercise."""
        from pytgcalls.types import Device, StreamEnded

        calls = FakeCalls()
        manager = VoiceChatManager(calls)
        await manager.start()
        directory = tempfile.TemporaryDirectory()
        audio_file = Path(directory.name) / "track.ogg"
        audio_file.write_bytes(b"audio")
        await manager.play(-100123, str(audio_file), Playback(directory, "Track"))

        await manager._on_update(
            calls,
            StreamEnded(-100123, StreamEnded.Type.AUDIO, Device.SPEAKER),
        )

        assert calls.left == [-100123]
        assert not audio_file.exists()

    asyncio.run(exercise())


def test_shutdown_waits_for_inflight_play_and_closes_its_session():
    """Shutdown waits for inflight play and closes its session."""

    class BlockingCalls(FakeCalls):
        """Blocking calls."""

        def __init__(self):
            """Init."""
            super().__init__()
            self.play_entered = asyncio.Event()
            self.allow_play_to_finish = asyncio.Event()

        async def play(self, chat_id, path, *, config):
            """Play."""
            self.play_entered.set()
            await self.allow_play_to_finish.wait()
            await super().play(chat_id, path, config=config)

    async def exercise():
        """Exercise."""
        calls = BlockingCalls()
        manager = VoiceChatManager(calls)
        await manager.start()
        directory = tempfile.TemporaryDirectory()
        audio_file = Path(directory.name) / "track.ogg"
        audio_file.write_bytes(b"audio")

        play_task = asyncio.create_task(
            manager.play(-100123, str(audio_file), Playback(directory, "Track"))
        )
        await calls.play_entered.wait()
        shutdown_task = asyncio.create_task(manager.shutdown())
        await asyncio.sleep(0)
        assert not shutdown_task.done(), "shutdown must wait for the in-flight play"

        calls.allow_play_to_finish.set()
        await asyncio.gather(play_task, shutdown_task)

        assert calls.played == [(-100123, str(audio_file), False)]
        assert calls.left == [-100123]
        assert not audio_file.exists()
        assert manager._sessions == {}
        assert manager._closed

    asyncio.run(exercise())


def test_native_voice_client_initializes_inside_asyncio_lifecycle(monkeypatch):
    """Native voice client initializes inside asyncio lifecycle."""
    monkeypatch.setattr(voice._state, "manager", None)

    async def exercise():
        """Exercise."""
        manager = voice.initialize_voice()
        assert isinstance(manager, VoiceChatManager)

    asyncio.run(exercise())
