import math
from unittest.mock import patch

from botlite.utils.system import check_cooldown, free_disk


def test_check_cooldown_when_ready_and_waiting():
    with patch("botlite.utils.system.USER_COOLDOWN", 5):
        with patch("time.time", return_value=100.0):
            assert math.isclose(check_cooldown({}, 10), 0.0, abs_tol=1e-9)

        with patch("time.time", return_value=100.0):
            remaining = check_cooldown({10: 98.5}, 10)
            assert 3.4 <= remaining <= 3.6


def test_check_cooldown_disabled():
    with patch("botlite.utils.system.USER_COOLDOWN", 0):
        assert math.isclose(check_cooldown({1: 9999.0}, 1), 0.0, abs_tol=1e-9)


def test_free_disk_handles_failure():
    with patch("shutil.disk_usage", side_effect=OSError("boom")):
        assert free_disk(".") == 0


def test_cleanup_old_temps(tmp_path, monkeypatch):
    from botlite.utils.system import cleanup_old_temps

    stale_dir = tmp_path / "botlite_stale"
    stale_dir.mkdir()
    stale_file = stale_dir / "data.tmp"
    stale_file.write_bytes(b"temp")

    fresh_dir = tmp_path / "botlite_fresh"
    fresh_dir.mkdir()

    now = 10000.0
    monkeypatch.setattr("time.time", lambda: now)
    monkeypatch.setattr("glob.glob", lambda pat: [str(stale_dir), str(fresh_dir)])

    # Stale dir modified 5000s ago (> 3600)
    # Fresh dir modified 100s ago (< 3600)
    def fake_getmtime(path):
        if "stale" in path:
            return now - 5000.0
        return now - 100.0

    monkeypatch.setattr("os.path.getmtime", fake_getmtime)

    cleanup_old_temps()

    assert not stale_dir.exists()
    assert fresh_dir.exists()
