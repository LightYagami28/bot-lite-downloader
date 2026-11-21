"""Tests for config."""

import pytest

from botlite import config
from botlite.config import _int_list, _nonzero_int_list


def test_int_list_keeps_signed_decimal_ids_and_ignores_malformed_items(monkeypatch):
    """Int list keeps signed decimal ids and ignores malformed items."""
    monkeypatch.setenv("TEST_ID_LIST", "-100123, 42, --7, nope, 0, +9, ,")

    assert _int_list("TEST_ID_LIST") == [-100123, 42, 0, 9]
    assert _nonzero_int_list("TEST_ID_LIST") == {-100123, 42, 9}


def test_voice_requires_enabled_group_allowlist(monkeypatch):
    """Voice requires enabled group allowlist."""
    monkeypatch.setattr(config, "VOICE_ENABLED", True)
    monkeypatch.setattr(config, "ALLOW_GROUPS", False)
    monkeypatch.setattr(config, "ALLOWED_GROUP_IDS", set())

    with pytest.raises(SystemExit):
        config.validate()


def test_voice_configuration_accepts_explicit_group_allowlist(monkeypatch):
    """Voice configuration accepts explicit group allowlist."""
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
    """Helpers int and bool."""
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


def test_secret_files_take_precedence_and_fall_back_to_environment(monkeypatch, tmp_path):
    """Credentials are read from mounted files before environment variables."""
    monkeypatch.setattr(config, "_CREDENTIAL_FILES_DIR", str(tmp_path))
    monkeypatch.setenv("API_ID", "7")
    monkeypatch.setenv("API_HASH", "from-env")
    monkeypatch.setenv("SUDO_USERS", "42")

    assert config._secret("API_HASH") == "from-env"
    assert config._secret_int("API_ID", 0) == 7

    (tmp_path / "API_ID").write_text("123\n", encoding="utf-8")
    (tmp_path / "API_HASH").write_text("from-file\n", encoding="utf-8")
    (tmp_path / "BOT_TOKEN").write_text("token-from-file\n", encoding="utf-8")
    (tmp_path / "SUDO_USERS").write_text("-100123, 42, nope\n", encoding="utf-8")

    assert config._secret("API_HASH") == "from-file"
    assert config._secret_int("API_ID", 0) == 123
    assert config._secret("BOT_TOKEN") == "token-from-file"
    assert config._secret_id_set("SUDO_USERS") == {-100123, 42}

    (tmp_path / "API_HASH").unlink()
    (tmp_path / "API_HASH").mkdir()
    assert config._secret("API_HASH") == "from-env"

    (tmp_path / "API_ID").write_text("not-a-number", encoding="utf-8")
    assert config._secret_int("API_ID", 0) == 0


def test_validate_missing_required_fields(monkeypatch):
    """Validate missing required fields."""
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
