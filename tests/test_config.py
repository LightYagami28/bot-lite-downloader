import pytest

from botlite import config
from botlite.config import _int_list, _nonzero_int_list


def test_int_list_keeps_signed_decimal_ids_and_ignores_malformed_items(monkeypatch):
    monkeypatch.setenv("TEST_ID_LIST", "-100123, 42, --7, nope, 0, +9, ,")

    assert _int_list("TEST_ID_LIST") == [-100123, 42, 0, 9]
    assert _nonzero_int_list("TEST_ID_LIST") == {-100123, 42, 9}


def test_voice_requires_enabled_group_allowlist(monkeypatch):
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "ALLOW_GROUPS", False)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", set())

    with pytest.raises(SystemExit):
        config.validate()


def test_voice_configuration_accepts_explicit_group_allowlist(monkeypatch):
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "ALLOW_GROUPS", True)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", {-100123})
    monkeypatch.setattr(config, "VOICE_MAX_DURATION", 600)
    monkeypatch.setattr(config, "VOICE_MAX_FILE_SIZE", 50 * 1024 * 1024)

    config.validate()
