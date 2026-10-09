import asyncio

from botlite.handlers import commands


class FakeMessage:
    def __init__(self):
        self.edits = []

    async def edit(self, text, **kwargs):
        self.edits.append((text, kwargs))


class FakeEvent:
    def __init__(self, *, chat_id=-100123, is_group=True, sender_id=42):
        self.chat_id = chat_id
        self.is_group = is_group
        self.is_private = not is_group
        self.sender_id = sender_id
        self.raw_text = "/play https://media.example/track"
        self.replies = []

    async def reply(self, text, **kwargs):
        self.replies.append((text, kwargs))
        self.status = FakeMessage()
        return self.status


def test_voice_command_downloads_only_for_explicitly_allowed_group(monkeypatch):
    class FakeVoiceManager:
        def __init__(self):
            self.play_request = None

        async def play(self, chat_id, path, title, directory):
            self.play_request = (chat_id, path, title, directory)

    async def exercise():
        event = FakeEvent()
        manager = FakeVoiceManager()
        monkeypatch.setattr(commands, "VOICE_ENABLED", True)
        monkeypatch.setattr(commands, "ALLOW_GROUPS", True)
        monkeypatch.setattr(commands, "ALLOWED_GROUP_IDS", {-100123})
        monkeypatch.setattr(commands.db, "is_banned", lambda _user_id: False)
        monkeypatch.setattr(commands, "get_voice_manager", lambda: manager)

        async def download(_url, _directory, *, max_file_size, max_duration):
            assert max_file_size == commands.VOICE_MAX_FILE_SIZE
            assert max_duration == commands.VOICE_MAX_DURATION
            return "/tmp/audio.ogg", {"title": "Test track", "size": 10}

        monkeypatch.setattr(commands, "download_audio", download)
        commands._user_cooldowns.pop(event.sender_id, None)
        commands.active_downloads.discard(event.sender_id)
        try:
            await commands.cmd_voice_play(event)
            chat_id, path, title, directory = manager.play_request
            assert (chat_id, path, title) == (-100123, "/tmp/audio.ogg", "Test track")
            assert event.status.edits[0][1]["parse_mode"] == "html"
            directory.cleanup()
        finally:
            commands.active_downloads.discard(event.sender_id)
            commands._user_cooldowns.pop(event.sender_id, None)

    asyncio.run(exercise())


def test_voice_command_ignores_unallowlisted_group(monkeypatch):
    async def exercise():
        event = FakeEvent(chat_id=-100999)
        monkeypatch.setattr(commands, "VOICE_ENABLED", True)
        monkeypatch.setattr(commands, "ALLOW_GROUPS", True)
        monkeypatch.setattr(commands, "ALLOWED_GROUP_IDS", {-100123})

        async def forbidden_download(*_args, **_kwargs):
            raise AssertionError("voice download started in a non-allowlisted group")

        monkeypatch.setattr(commands, "download_audio", forbidden_download)
        await commands.cmd_voice_play(event)

        assert event.replies == []

    asyncio.run(exercise())
