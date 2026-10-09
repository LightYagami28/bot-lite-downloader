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
