import asyncio
from unittest.mock import AsyncMock, MagicMock

from botlite import app


def test_app_main_lifecycle(monkeypatch):
    async def exercise():
        actions = []

        monkeypatch.setattr(app.config, "validate", lambda: actions.append("config.validate"))
        monkeypatch.setattr(app, "setup_signals", lambda fn: actions.append("setup_signals"))
        monkeypatch.setattr(app, "cleanup_old_temps", lambda: actions.append("cleanup_old_temps"))
        monkeypatch.setattr(app.db, "init", lambda: actions.append("db.init"))

        # Client mocks
        mock_client = MagicMock()
        mock_client.start = AsyncMock(side_effect=lambda **kw: actions.append("client.start"))
        mock_client.run_until_disconnected = AsyncMock(
            side_effect=lambda: actions.append("client.run")
        )
        mock_client.disconnect = AsyncMock(side_effect=lambda: actions.append("client.disconnect"))
        monkeypatch.setattr(app, "client", mock_client)

        # Voice & WebApp disabled
        monkeypatch.setattr(app, "VOICE_ENABLED", False)
        monkeypatch.setattr(app, "WEBAPP_PUBLIC_URL", "")

        await app._main()

        assert "config.validate" in actions
        assert "setup_signals" in actions
        assert "cleanup_old_temps" in actions
        assert "db.init" in actions
        assert "client.start" in actions
        assert "client.run" in actions
        assert "client.disconnect" in actions

    asyncio.run(exercise())


def test_app_main_with_voice_and_webapp(monkeypatch):
    async def exercise():
        actions = []

        monkeypatch.setattr(app.config, "validate", lambda: None)
        monkeypatch.setattr(app, "setup_signals", lambda fn: None)
        monkeypatch.setattr(app, "cleanup_old_temps", lambda: None)
        monkeypatch.setattr(app.db, "init", lambda: None)

        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.run_until_disconnected = AsyncMock()
        mock_client.disconnect = AsyncMock(side_effect=lambda: actions.append("client.disconnect"))
        monkeypatch.setattr(app, "client", mock_client)

        monkeypatch.setattr(app, "VOICE_ENABLED", True)
        monkeypatch.setattr(app, "WEBAPP_PUBLIC_URL", "https://example.com/app")

        voice_mgr = MagicMock()
        voice_mgr.start = AsyncMock(side_effect=lambda: actions.append("voice.start"))
        voice_mgr.shutdown = AsyncMock(side_effect=lambda: actions.append("voice.shutdown"))
        voice_mgr.cleanup_after_disconnect = MagicMock(
            side_effect=lambda: actions.append("voice.cleanup")
        )
        monkeypatch.setattr(app, "initialize_voice", lambda: voice_mgr)
        monkeypatch.setattr(app, "get_voice_manager", lambda: voice_mgr)

        import sys

        mock_webapp_mod = MagicMock()
        mock_webapp_mod.start_webapp = AsyncMock(side_effect=lambda: actions.append("webapp.start"))
        mock_webapp_mod.stop_webapp = AsyncMock(side_effect=lambda: actions.append("webapp.stop"))
        monkeypatch.setitem(sys.modules, "botlite.webapp", mock_webapp_mod)

        await app._main()

        assert "voice.start" in actions
        assert "webapp.start" in actions
        assert "voice.shutdown" in actions
        assert "webapp.stop" in actions
        assert "client.disconnect" in actions
        assert "voice.cleanup" in actions

    asyncio.run(exercise())
