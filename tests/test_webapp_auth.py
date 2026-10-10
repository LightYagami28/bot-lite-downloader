import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any
from unittest.mock import patch

from botlite.webapp.auth import validate_init_data


def _build_init_data(bot_token: str, user: dict[str, Any]) -> str:
    params = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHx",
        "user": json.dumps(user, separators=(",", ":")),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    digest = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = digest
    return urllib.parse.urlencode(params)


def test_validate_init_data_success():
    init_data = _build_init_data("token123", {"id": 42, "username": "admin"})
    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        user_data = validate_init_data(init_data)
    assert user_data is not None
    assert user_data.get("id") == 42


def test_validate_init_data_failures():
    with patch("botlite.webapp.auth.BOT_TOKEN", ""):
        assert validate_init_data("a=b") is None

    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        assert validate_init_data("") is None
        assert validate_init_data("auth_date=1") is None
        assert validate_init_data("hash=abc&auth_date=1") is None


def test_validate_init_data_invalid_user_json_is_rejected():
    params = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHx",
        "user": "{bad-json}",
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", b"token123", hashlib.sha256).digest()
    digest = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    init_data = urllib.parse.urlencode({**params, "hash": digest})

    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        assert validate_init_data(init_data) is None


def test_validate_init_data_rejects_expired_data():
    init_data = _build_init_data("token123", {"id": 42})
    with (
        patch("botlite.webapp.auth.BOT_TOKEN", "token123"),
        patch("botlite.webapp.auth.WEBAPP_INIT_DATA_MAX_AGE", 0),
    ):
        assert validate_init_data(init_data) is None


def test_validate_init_data_rejects_duplicate_parameters():
    init_data = _build_init_data("token123", {"id": 42})
    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        assert validate_init_data(f"{init_data}&auth_date=invalid") is None


def test_validate_init_data_rejects_invalid_user_payload():
    params = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHx",
        "user": "[]",
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", b"token123", hashlib.sha256).digest()
    digest = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    init_data = urllib.parse.urlencode({**params, "hash": digest})

    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        assert validate_init_data(init_data) is None


def test_validate_init_data_rejects_oversized_payload():
    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        assert validate_init_data("a=" + ("x" * 8192)) is None


def test_validate_init_data_rejects_boolean_user_id():
    init_data = _build_init_data("token123", {"id": True})
    with patch("botlite.webapp.auth.BOT_TOKEN", "token123"):
        assert validate_init_data(init_data) is None
