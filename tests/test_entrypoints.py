"""Gli entry point `python run.py` e `python -m botlite` avviano il bot."""

import runpy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


def test_run_py_starts_the_bot():
    with patch("botlite.app.run") as run:
        runpy.run_path(str(ROOT / "run.py"), run_name="__main__")
    run.assert_called_once_with()


def test_run_py_does_not_start_the_bot_when_imported():
    with patch("botlite.app.run") as run:
        runpy.run_path(str(ROOT / "run.py"), run_name="run")
    run.assert_not_called()


def test_module_entry_point_starts_the_bot():
    with patch("botlite.app.run") as run:
        runpy.run_module("botlite", run_name="__main__")
    run.assert_called_once_with()
