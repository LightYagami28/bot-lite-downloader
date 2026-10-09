import asyncio
import signal

from botlite.utils.system import setup_signals


def test_shutdown_signal_awaits_disconnect_and_ignores_duplicates(monkeypatch):
    async def exercise():
        handlers = {}
        monkeypatch.setattr(
            signal,
            "signal",
            lambda signum, handler: handlers.__setitem__(signum, handler),
        )
        disconnected = asyncio.Event()
        calls = 0

        async def disconnect():
            nonlocal calls
            calls += 1
            disconnected.set()

        setup_signals(disconnect)
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        handlers[signal.SIGINT](signal.SIGINT, None)
        await asyncio.wait_for(disconnected.wait(), timeout=1)
        await asyncio.sleep(0)

        assert calls == 1

    asyncio.run(exercise())
