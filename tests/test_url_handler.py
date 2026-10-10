import asyncio
from unittest.mock import MagicMock

from botlite.handlers import url


class FakeMessage:
    def __init__(self, text="", caption=None, msg_id=1):
        self.text = text
        self.caption = caption
        self.id = msg_id
        self.edits = []
        self.deleted = False

    async def edit(self, text, **kwargs):
        self.edits.append((text, kwargs))

    async def delete(self):
        self.deleted = True


class FakeEvent:
    def __init__(
        self,
        *,
        chat_id=1001,
        sender_id=42,
        is_private=True,
        is_group=False,
        text="",
        caption=None,
    ):
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.is_private = is_private
        self.is_group = is_group
        self.message = FakeMessage(text=text, caption=caption)
        self.replies = []
        self.status = FakeMessage()

    async def reply(self, text, **kwargs):
        self.replies.append((text, kwargs))
        return self.status


def test_url_handler_ignores_commands():
    async def exercise():
        event = FakeEvent(text="/start https://example.com/video")
        await url.url_handler(event)
        assert len(event.replies) == 0

    asyncio.run(exercise())


def test_url_handler_ignores_no_url():
    async def exercise():
        event = FakeEvent(text="Hello world, no link here!")
        await url.url_handler(event)
        assert len(event.replies) == 0

    asyncio.run(exercise())


def test_url_handler_ignores_tme_links():
    async def exercise():
        event = FakeEvent(text="Check this out: https://t.me/somechannel/123")
        await url.url_handler(event)
        assert len(event.replies) == 0

    asyncio.run(exercise())


def test_check_guards_banned(monkeypatch):
    async def exercise():
        monkeypatch.setattr(url.db, "is_banned", lambda uid: True)
        event = FakeEvent(sender_id=42)
        rejected = await url._check_guards(event, 42)
        assert rejected is True
        assert "banned" in event.replies[0][0]

    asyncio.run(exercise())


def test_check_guards_active_download(monkeypatch):
    async def exercise():
        monkeypatch.setattr(url.db, "is_banned", lambda uid: False)
        event = FakeEvent(sender_id=42)
        url.active_downloads.add(42)
        try:
            rejected = await url._check_guards(event, 42)
            assert rejected is True
            assert "still running" in event.replies[0][0]
        finally:
            url.active_downloads.discard(42)

    asyncio.run(exercise())


def test_check_guards_cooldown(monkeypatch):
    async def exercise():
        monkeypatch.setattr(url.db, "is_banned", lambda uid: False)
        monkeypatch.setattr(url, "check_cooldown", lambda cooldowns, uid: 15.0)
        event = FakeEvent(sender_id=42)
        rejected = await url._check_guards(event, 42)
        assert rejected is True
        assert "Please wait **15s**" in event.replies[0][0]

    asyncio.run(exercise())


def test_check_guards_low_disk(monkeypatch):
    async def exercise():
        monkeypatch.setattr(url.db, "is_banned", lambda uid: False)
        monkeypatch.setattr(url, "check_cooldown", lambda cooldowns, uid: 0.0)
        monkeypatch.setattr(url, "free_disk", lambda: 100)  # low disk
        event = FakeEvent(sender_id=42)
        rejected = await url._check_guards(event, 42)
        assert rejected is True
        assert "low on disk space" in event.replies[0][0]

    asyncio.run(exercise())


def test_upload_results_skips_oversized_files(tmp_path):
    async def exercise():
        oversized = tmp_path / "big.mp4"
        oversized.write_bytes(b"x" * 2000)

        normal = tmp_path / "normal.jpg"
        normal.write_bytes(b"x" * 100)

        event = FakeEvent()
        status = FakeMessage()

        sent_files = []

        async def fake_send_media(ev, fp, meta, mtype):
            sent_files.append((fp, mtype))

        orig_send = url._send_media
        url._send_media = fake_send_media

        # MAX_FILE_SIZE = 1000
        orig_max = url.MAX_FILE_SIZE
        url.MAX_FILE_SIZE = 1000

        try:
            results = [
                (str(oversized), {"title": "Big"}, "video"),
                (str(normal), {"title": "Normal"}, "photo"),
            ]
            sent_count = await url._upload_results(event, status, results)
            assert sent_count == 1
            assert len(event.replies) == 1
            assert "skipped — too large" in event.replies[0][0]
            assert len(sent_files) == 1
            assert sent_files[0][0] == str(normal)
        finally:
            url._send_media = orig_send
            url.MAX_FILE_SIZE = orig_max

    asyncio.run(exercise())


def test_url_handler_success(tmp_path, monkeypatch):
    async def exercise():
        test_file = tmp_path / "video.mp4"
        test_file.write_bytes(b"x" * 500)

        fake_results = [
            (str(test_file), {"title": "Sample", "uploader": "Artist", "duration": 10}, "video")
        ]

        async def mock_download(url_arg):
            return str(tmp_path), fake_results

        monkeypatch.setattr(url, "download", mock_download)
        monkeypatch.setattr(url.db, "is_banned", lambda uid: False)
        monkeypatch.setattr(url, "check_cooldown", lambda c, u: 0.0)
        monkeypatch.setattr(url, "free_disk", lambda: 1024 * 1024 * 1024 * 10)

        sent_calls = []

        async def mock_send_file(chat_id, fp, **kwargs):
            sent_calls.append((chat_id, fp, kwargs))

        monkeypatch.setattr(url.client, "send_file", mock_send_file)

        stats_incremented = []
        monkeypatch.setattr(url.db, "increment", lambda name: stats_incremented.append(name))

        event = FakeEvent(text="Check this video: https://youtube.com/watch?v=abcd")
        await url.url_handler(event)

        assert len(sent_calls) == 1
        assert "total_downloads" in stats_incremented
        assert event.status.deleted is True

    asyncio.run(exercise())


def test_url_handler_download_failure(monkeypatch):
    async def exercise():
        async def mock_download(url_arg):
            raise RuntimeError("Extraction failed completely")

        monkeypatch.setattr(url, "download", mock_download)
        monkeypatch.setattr(url.db, "is_banned", lambda uid: False)
        monkeypatch.setattr(url, "check_cooldown", lambda c, u: 0.0)
        monkeypatch.setattr(url, "free_disk", lambda: 1024 * 1024 * 1024 * 10)

        stats_incremented = []
        monkeypatch.setattr(url.db, "increment", lambda name: stats_incremented.append(name))

        event = FakeEvent(text="Download this: https://bad-url.com/something")
        await url.url_handler(event)

        assert "failed_downloads" in stats_incremented
        assert any("Download failed" in edit[0] for edit in event.status.edits)

    asyncio.run(exercise())


def test_safe_edit():
    async def exercise():
        msg = FakeMessage()
        await url._safe_edit(msg, "new text")
        assert msg.edits[0][0] == "new text"

        # Safe edit tolerates errors
        broken_msg = MagicMock()
        broken_msg.edit.side_effect = RuntimeError("network dropped")
        await url._safe_edit(broken_msg, "fail text")  # Should not raise

    asyncio.run(exercise())
