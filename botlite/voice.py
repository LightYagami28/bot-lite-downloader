"""Opt-in Telegram group voice-chat playback backed by PyTgCalls."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass

from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NotInCallError
from pytgcalls.types import GroupCallConfig, StreamEnded

from botlite.client import client
from botlite.errors import RECOVERABLE_ERRORS

log = logging.getLogger("botlite.voice")


@dataclass
class _Playback:
    directory: tempfile.TemporaryDirectory[str]
    title: str


class VoiceChatManager:
    """Own one audio stream per allowlisted group and its temporary files."""

    def __init__(self, calls) -> None:
        """Bind to *calls* and register the stream-end update listener."""
        self._calls = calls
        self._sessions: dict[int, _Playback] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._started = False
        self._closed = False
        self._calls.on_update()(self._on_update)

    async def start(self) -> None:
        """Start the underlying call client once."""
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
        """Play *path* in chat *chat_id*, replacing any existing stream."""
        if not self._started or self._closed:
            raise RuntimeError("Voice playback is not running")
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
        """Pause the stream in *chat_id*; return False when there is none."""
        if chat_id not in self._sessions:
            return False
        return bool(await self._calls.pause(chat_id))

    async def resume(self, chat_id: int) -> bool:
        """Resume the stream in *chat_id*; return False when there is none."""
        if chat_id not in self._sessions:
            return False
        return bool(await self._calls.resume(chat_id))

    async def stop(self, chat_id: int) -> bool:
        """Stop the stream in *chat_id*; return False when there is none."""
        async with self._lock_for(chat_id):
            if chat_id not in self._sessions:
                return False
            await self._leave_existing(chat_id)
            return True

    async def shutdown(self) -> None:
        """Stop every session and close the manager; safe to call twice."""
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
                except RECOVERABLE_ERRORS:
                    log.exception(
                        "Unable to leave voice chat %s during shutdown", chat_id
                    )

    def cleanup_after_disconnect(self) -> None:
        """Release temporary files only after the MTProto connection is closed."""
        for playback in self._sessions.values():
            playback.directory.cleanup()
        self._sessions.clear()

    async def _leave_existing(self, chat_id: int) -> None:
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
        if not isinstance(update, StreamEnded):
            return
        chat_id = update.chat_id
        if chat_id not in self._sessions:
            return
        try:
            async with self._lock_for(chat_id):
                await self._leave_existing(chat_id)
        except RECOVERABLE_ERRORS:
            log.exception("Unable to clean up ended playback in chat %s", chat_id)


@dataclass
class _State:
    manager: VoiceChatManager | None = None


_state = _State()


def initialize_voice() -> VoiceChatManager:
    """Create the voice manager once the asyncio loop is running."""
    if _state.manager is None:
        _state.manager = VoiceChatManager(PyTgCalls(client))
    return _state.manager


def get_voice_manager() -> VoiceChatManager:
    """Return the initialized voice manager, raising when voice is unavailable."""
    if _state.manager is None:
        raise RuntimeError("Voice playback is disabled or not initialized")
    return _state.manager
