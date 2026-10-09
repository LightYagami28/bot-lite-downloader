"""Opt-in Telegram group voice-chat playback backed by PyTgCalls."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass

from botlite.client import client

log = logging.getLogger("botlite.voice")


@dataclass
class _Playback:
    directory: tempfile.TemporaryDirectory[str]
    title: str


class VoiceChatManager:
    """Own one audio stream per allowlisted group and its temporary files."""

    def __init__(self, calls) -> None:
        self._calls = calls
        self._sessions: dict[int, _Playback] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._started = False
        self._closed = False
        self._calls.on_update()(self._on_update)

    async def start(self) -> None:
        if self._started:
            return
        await self._calls.start()
        self._started = True

    def _lock_for(self, chat_id: int) -> asyncio.Lock:
        return self._locks.setdefault(chat_id, asyncio.Lock())

    async def play(
        self,
        chat_id: int,
        path: str,
        title: str,
        directory: tempfile.TemporaryDirectory[str],
    ) -> None:
        if not self._started or self._closed:
            raise RuntimeError("Voice playback is not running")
        from pytgcalls.types import GroupCallConfig

        async with self._lock_for(chat_id):
            # The caller may have been queued behind another operation while
            # shutdown began. Recheck the lifecycle state after taking the
            # per-chat lock, before creating a new remote stream.
            if not self._started or self._closed:
                raise RuntimeError("Voice playback is not running")
            await self._leave_existing(chat_id)
            await self._calls.play(
                chat_id,
                path,
                config=GroupCallConfig(auto_start=False),
            )
            self._sessions[chat_id] = _Playback(directory, title)

    async def pause(self, chat_id: int) -> bool:
        if chat_id not in self._sessions:
            return False
        return bool(await self._calls.pause(chat_id))

    async def resume(self, chat_id: int) -> bool:
        if chat_id not in self._sessions:
            return False
        return bool(await self._calls.resume(chat_id))

    async def stop(self, chat_id: int) -> bool:
        async with self._lock_for(chat_id):
            if chat_id not in self._sessions:
                return False
            await self._leave_existing(chat_id)
            return True

    async def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Include in-flight play operations as well as established sessions.
        # Setting _closed above prevents new plays; taking every existing lock
        # waits for a play already inside its critical section, then observes
        # and closes the session it created.
        for chat_id in tuple(self._locks):
            async with self._lock_for(chat_id):
                if chat_id not in self._sessions:
                    continue
                try:
                    await self._leave_existing(chat_id)
                except Exception:
                    log.exception(
                        "Unable to leave voice chat %s during shutdown", chat_id
                    )

    def cleanup_after_disconnect(self) -> None:
        """Release temporary files only after the MTProto connection is closed."""
        for playback in self._sessions.values():
            playback.directory.cleanup()
        self._sessions.clear()

    async def _leave_existing(self, chat_id: int) -> None:
        from pytgcalls.exceptions import NotInCallError

        playback = self._sessions.get(chat_id)
        if playback is None:
            return
        try:
            await self._calls.leave_call(chat_id)
        except NotInCallError:
            log.info("Voice call already ended in chat %s", chat_id)
        else:
            log.info("Left voice chat %s", chat_id)
        self._sessions.pop(chat_id, None)
        playback.directory.cleanup()

    async def _on_update(self, _calls: object, update: object) -> None:
        from pytgcalls.types import StreamEnded

        if not isinstance(update, StreamEnded):
            return
        chat_id = update.chat_id
        if chat_id not in self._sessions:
            return
        try:
            async with self._lock_for(chat_id):
                await self._leave_existing(chat_id)
        except Exception:
            log.exception("Unable to clean up ended playback in chat %s", chat_id)


_voice_manager: VoiceChatManager | None = None


def initialize_voice() -> VoiceChatManager:
    """Load the native voice stack after the asyncio loop has been created."""
    global _voice_manager
    if _voice_manager is None:
        from pytgcalls import PyTgCalls

        _voice_manager = VoiceChatManager(PyTgCalls(client))
    return _voice_manager


def get_voice_manager() -> VoiceChatManager:
    if _voice_manager is None:
        raise RuntimeError("Voice playback is disabled or not initialized")
    return _voice_manager
