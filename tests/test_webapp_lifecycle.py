import asyncio

import pytest

from botlite import webapp


def test_webapp_runner_starts_stops_and_allows_idempotent_cleanup(monkeypatch):
    monkeypatch.setattr(webapp, "WEBAPP_HOST", "127.0.0.1")
    monkeypatch.setattr(webapp, "WEBAPP_PORT", 0)

    async def exercise():
        await webapp.start_webapp()
        assert webapp._runner is not None

        await webapp.stop_webapp()
        assert webapp._runner is None
        await webapp.stop_webapp()

    asyncio.run(exercise())


def test_webapp_rejects_duplicate_start_and_still_cleans_up(monkeypatch):
    monkeypatch.setattr(webapp, "WEBAPP_HOST", "127.0.0.1")
    monkeypatch.setattr(webapp, "WEBAPP_PORT", 0)

    async def exercise():
        await webapp.start_webapp()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                await webapp.start_webapp()
        finally:
            await webapp.stop_webapp()

    asyncio.run(exercise())
