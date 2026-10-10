import asyncio
from unittest.mock import MagicMock

from botlite.handlers import commands


class FakeEvent:
    def __init__(
        self,
        *,
        chat_id=123,
        sender_id=100,
        is_private=True,
        is_group=False,
        text="",
        pattern_match=None,
    ):
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.is_private = is_private
        self.is_group = is_group
        self.raw_text = text
        self.pattern_match = pattern_match
        self.replies = []

    async def reply(self, text, **kwargs):
        self.replies.append((text, kwargs))
        msg = MagicMock()
        msg.edit = MagicMock()
        return msg


def test_is_sudo(monkeypatch):
    monkeypatch.setattr(commands, "SUDO_USERS", [111, 222])
    assert commands.is_sudo(111) is True
    assert commands.is_sudo(999) is False


def test_dashboard_button(monkeypatch):
    monkeypatch.setattr(commands, "WEBAPP_PUBLIC_URL", "")
    assert commands._dashboard_button() is None

    monkeypatch.setattr(commands, "WEBAPP_PUBLIC_URL", "https://example.com/app")
    btn = commands._dashboard_button()
    assert btn is not None
    assert len(btn) == 1


def test_cmd_start():
    async def exercise():
        event = FakeEvent(is_private=True, is_group=False)
        await commands.cmd_start(event)
        assert len(event.replies) == 1
        text, kwargs = event.replies[0]
        assert "Bot Lite Downloader" in text
        assert kwargs.get("parse_mode") == "md"

    asyncio.run(exercise())


def test_cmd_help(monkeypatch):
    async def exercise():
        monkeypatch.setattr(commands, "USER_COOLDOWN", 10)
        monkeypatch.setattr(commands, "VOICE_ENABLED", False)
        event = FakeEvent(is_private=True, is_group=False)
        await commands.cmd_help(event)
        assert len(event.replies) == 1
        text, _ = event.replies[0]
        assert "Cooldown between requests: 10s" in text
        assert "Limits" in text

    asyncio.run(exercise())


def test_cmd_status(monkeypatch):
    async def exercise():
        monkeypatch.setattr(commands, "free_disk", lambda: 1024 * 1024 * 1024 * 10)
        event = FakeEvent(is_private=True, is_group=False)
        await commands.cmd_status(event)
        assert len(event.replies) == 1
        text, _ = event.replies[0]
        assert "Uptime:" in text
        assert "Free disk:" in text

    asyncio.run(exercise())


def test_cmd_stats(monkeypatch):
    async def exercise():
        monkeypatch.setattr(commands, "SUDO_USERS", [100])
        monkeypatch.setattr(
            commands.db, "get_stat", lambda name: 42 if name == "total_downloads" else 3
        )
        monkeypatch.setattr(commands, "free_disk", lambda: 1024 * 1024 * 1024 * 5)

        # Sudo user
        event_sudo = FakeEvent(sender_id=100, is_private=True)
        await commands.cmd_stats(event_sudo)
        assert len(event_sudo.replies) == 1
        assert "Succeeded: `42`" in event_sudo.replies[0][0]

        # Non-sudo user
        event_non_sudo = FakeEvent(sender_id=999, is_private=True)
        await commands.cmd_stats(event_non_sudo)
        assert len(event_non_sudo.replies) == 0

        # Sudo user in group (must be ignored)
        event_group = FakeEvent(sender_id=100, is_private=False, is_group=True)
        await commands.cmd_stats(event_group)
        assert len(event_group.replies) == 0

    asyncio.run(exercise())


def test_cmd_ban_and_unban(monkeypatch):
    async def exercise():
        monkeypatch.setattr(commands, "SUDO_USERS", [100])
        banned = []
        unbanned = []
        monkeypatch.setattr(commands.db, "ban", lambda uid: banned.append(uid))
        monkeypatch.setattr(commands.db, "unban", lambda uid: unbanned.append(uid))

        match_mock = MagicMock()
        match_mock.group.return_value = " 555"

        event = FakeEvent(sender_id=100, is_private=True, pattern_match=match_mock)
        await commands.cmd_ban(event)
        assert banned == [555]
        assert "banned" in event.replies[0][0]

        await commands.cmd_unban(event)
        assert unbanned == [555]
        assert "unbanned" in event.replies[1][0]

        # Missing user ID
        match_empty = MagicMock()
        match_empty.group.return_value = None
        event_empty = FakeEvent(sender_id=100, is_private=True, pattern_match=match_empty)
        await commands.cmd_ban(event_empty)
        assert "Usage: `/ban USER_ID`" in event_empty.replies[0][0]

        await commands.cmd_unban(event_empty)
        assert "Usage: `/unban USER_ID`" in event_empty.replies[1][0]

    asyncio.run(exercise())


def test_cmd_voice_control(monkeypatch):
    class FakeVoiceManager:
        def __init__(self):
            self.action = None

        async def pause(self, chat_id):
            self.action = "pause"
            return True

        async def resume(self, chat_id):
            self.action = "resume"
            return False

        async def stop(self, chat_id):
            self.action = "stop"
            return True

    async def exercise():
        mgr = FakeVoiceManager()
        monkeypatch.setattr(commands, "VOICE_ENABLED", True)
        monkeypatch.setattr(commands, "ALLOW_GROUPS", True)
        monkeypatch.setattr(commands, "ALLOWED_GROUP_IDS", {123})
        monkeypatch.setattr(commands, "get_voice_manager", lambda: mgr)

        # Pause
        match_pause = MagicMock()
        match_pause.group.return_value = "pause"
        event = FakeEvent(chat_id=123, is_group=True, is_private=False, pattern_match=match_pause)
        await commands.cmd_voice_control(event)
        assert "Playback paused" in event.replies[0][0]

        # Resume (returns False -> not paused)
        match_resume = MagicMock()
        match_resume.group.return_value = "resume"
        event_resume = FakeEvent(
            chat_id=123, is_group=True, is_private=False, pattern_match=match_resume
        )
        await commands.cmd_voice_control(event_resume)
        assert "No paused playback" in event_resume.replies[0][0]

        # Stop
        match_stop = MagicMock()
        match_stop.group.return_value = "voice_stop"
        event_stop = FakeEvent(
            chat_id=123, is_group=True, is_private=False, pattern_match=match_stop
        )
        await commands.cmd_voice_control(event_stop)
        assert "Playback stopped" in event_stop.replies[0][0]

    asyncio.run(exercise())


def test_cmd_voice_play_guards(monkeypatch):
    async def exercise():
        monkeypatch.setattr(commands, "VOICE_ENABLED", True)
        monkeypatch.setattr(commands, "ALLOW_GROUPS", True)
        monkeypatch.setattr(commands, "ALLOWED_GROUP_IDS", {123})

        # Banned user
        monkeypatch.setattr(commands.db, "is_banned", lambda uid: True)
        event_banned = FakeEvent(
            chat_id=123, is_group=True, is_private=False, text="/play https://example.com/audio"
        )
        await commands.cmd_voice_play(event_banned)
        assert "You are banned" in event_banned.replies[0][0]

        # Active download
        monkeypatch.setattr(commands.db, "is_banned", lambda uid: False)
        commands.active_downloads.add(100)
        try:
            event_active = FakeEvent(
                chat_id=123, is_group=True, is_private=False, text="/play https://example.com/audio"
            )
            await commands.cmd_voice_play(event_active)
            assert "still running" in event_active.replies[0][0]
        finally:
            commands.active_downloads.discard(100)

        # Bad syntax
        event_bad = FakeEvent(chat_id=123, is_group=True, is_private=False, text="/play")
        await commands.cmd_voice_play(event_bad)
        assert "Usage: `/play https://" in event_bad.replies[0][0]

    asyncio.run(exercise())
