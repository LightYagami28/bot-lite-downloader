"""Validate Telegram WebApp initData (HMAC-SHA256 per the official spec)."""

# https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

from botlite.config import BOT_TOKEN, WEBAPP_INIT_DATA_MAX_AGE

_MAX_INIT_DATA_LENGTH = 8 * 1024
_INIT_DATA_CLOCK_SKEW = 60  # seconds of client clock skew tolerated


def _query_pairs(init_data: str) -> list[tuple[str, str]]:
    """Parse initData preserving duplicate keys for explicit rejection.

    Args:
        init_data: Raw query-string sent by the Telegram Mini App.

    Returns:
        Decoded key/value pairs, or an empty list when parsing fails.
    """
    # Telegram signs the exact decoded key/value set. Reject duplicate keys
    # instead of silently accepting whichever value happens to win in a dict;
    # this prevents parser differentials between proxies and the application.
    try:
        return urllib.parse.parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
            max_num_fields=32,
        )
    except ValueError:
        return []


def _parse_fields(init_data: str) -> dict[str, str] | None:
    """Split initData into fields, rejecting malformed or duplicate-key input."""
    if not init_data or len(init_data) > _MAX_INIT_DATA_LENGTH:
        return None
    pairs = _query_pairs(init_data)
    params = dict(pairs)
    return params if pairs and len(params) == len(pairs) else None


def _signature_valid(params: dict[str, str], received_hash: str) -> bool:
    """Verify the HMAC-SHA256 signature using constant-time comparison.

    Args:
        params: Signed fields, excluding the ``hash`` field itself.
        received_hash: Hexadecimal hash supplied by Telegram.

    Returns:
        ``True`` when the signature matches.
    """
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    expected = hmac.new(
        key=secret_key,
        msg=data_check.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_hash)


def _fresh(params: dict[str, str]) -> bool:
    """Check that ``auth_date`` is recent and not too far in the future.

    Args:
        params: Parsed initData fields.

    Returns:
        ``True`` when the timestamp is within the accepted window.
    """
    try:
        age = time.time() - int(params["auth_date"])
    except (KeyError, TypeError, ValueError):
        return False
    return -_INIT_DATA_CLOCK_SKEW <= age <= WEBAPP_INIT_DATA_MAX_AGE


def _parse_user(params: dict[str, str]) -> dict[str, Any] | None:
    """Parse and minimally validate the signed ``user`` object.

    Args:
        params: Parsed initData fields.

    Returns:
        The user dictionary when it contains a positive integer id.
    """
    try:
        user = json.loads(params.get("user", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        return None
    return user


def _authentic(params: dict[str, str], received_hash: str) -> bool:
    """Require both a valid signature and a fresh timestamp.

    Args:
        params: Parsed initData fields.
        received_hash: Hexadecimal hash supplied by Telegram.

    Returns:
        ``True`` when both checks pass.
    """
    return _signature_valid(params, received_hash) and _fresh(params)


def validate_init_data(init_data: str) -> dict[str, Any] | None:
    """Validate the initData string sent by Telegram WebApp.

    Returns the parsed ``user`` dict on success, or ``None`` if the
    signature is missing, invalid, or the token is not configured.
    """
    params = _parse_fields(init_data) if BOT_TOKEN else None
    if params is None:
        return None
    received_hash = params.pop("hash", None)
    if not received_hash or not _authentic(params, received_hash):
        return None
    return _parse_user(params)
