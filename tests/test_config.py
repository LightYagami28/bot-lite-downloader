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
    monkeypatch.setattr(config, "API_ID", 123)
    monkeypatch.setattr(config, "API_HASH", "hash")
    monkeypatch.setattr(config, "BOT_TOKEN", "token")
    monkeypatch.setattr(config, "WEBAPP_PUBLIC_URL", "")
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "ALLOW_GROUPS", True)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", {-100123})
    monkeypatch.setattr(config, "VOICE_MAX_DURATION", 600)
    monkeypatch.setattr(config, "VOICE_MAX_FILE_SIZE", 50 * 1024 * 1024)

    config.validate()


def test_helpers_int_and_bool(monkeypatch):
    from botlite.config import _bool, _int

    # _int
    monkeypatch.setenv("TEST_INT_VALID", "42")
    monkeypatch.setenv("TEST_INT_INVALID", "not-a-number")
    assert _int("TEST_INT_VALID", 10) == 42
    assert _int("TEST_INT_INVALID", 10) == 10
    assert _int("TEST_INT_UNSET", 10) == 10

    # _bool
    monkeypatch.setenv("TEST_BOOL_TRUE1", "true")
    monkeypatch.setenv("TEST_BOOL_TRUE2", "1")
    monkeypatch.setenv("TEST_BOOL_TRUE3", "yes")
    monkeypatch.setenv("TEST_BOOL_FALSE1", "false")
    monkeypatch.setenv("TEST_BOOL_FALSE2", "0")
    monkeypatch.setenv("TEST_BOOL_FALSE3", "no")
    assert _bool("TEST_BOOL_TRUE1", False) is True
    assert _bool("TEST_BOOL_TRUE2", False) is True
    assert _bool("TEST_BOOL_TRUE3", False) is True
    assert _bool("TEST_BOOL_FALSE1", True) is False
    assert _bool("TEST_BOOL_FALSE2", True) is False
    assert _bool("TEST_BOOL_FALSE3", True) is False
    assert _bool("TEST_BOOL_UNSET", True) is True
    assert _bool("TEST_BOOL_UNSET", False) is False


def test_validate_missing_required_fields(monkeypatch):
    monkeypatch.setattr(config, "API_ID", 0)
    monkeypatch.setattr(config, "API_HASH", "")
    monkeypatch.setattr(config, "BOT_TOKEN", "")
    with pytest.raises(SystemExit):
        config.validate()

    # Valid base
    monkeypatch.setattr(config, "API_ID", 123)
    monkeypatch.setattr(config, "API_HASH", "hash")
    monkeypatch.setattr(config, "BOT_TOKEN", "token")
    monkeypatch.setattr(config, "VOICE_ENABLED", False)
    monkeypatch.setattr(config, "ALLOW_GROUPS", False)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", set())
    monkeypatch.setattr(config, "WEBAPP_PUBLIC_URL", "")

    # Invalid WebApp URL (must be HTTPS)
    monkeypatch.setattr(config, "WEBAPP_PUBLIC_URL", "http://insecure.test")
    with pytest.raises(SystemExit):
        config.validate()
    monkeypatch.setattr(config, "WEBAPP_PUBLIC_URL", "https://secure.test")
    config.validate()

    # Invalid ALLOW_GROUPS without ALLOWED_GROUP_IDS
    monkeypatch.setattr(config, "ALLOW_GROUPS", True)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", set())
    with pytest.raises(SystemExit):
        config.validate()

    # Invalid voice duration or size
    monkeypatch.setattr(config, "ALLOW_GROUPS", True)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", {123})
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "VOICE_MAX_DURATION", 0)
    with pytest.raises(SystemExit):
        config.validate()

    monkeypatch.setattr(config, "VOICE_MAX_DURATION", 100)
    monkeypatch.setattr(config, "VOICE_MAX_FILE_SIZE", 0)
    with pytest.raises(SystemExit):
        config.validate()
