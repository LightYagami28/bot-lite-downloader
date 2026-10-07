"""
botlite.webapp.auth
~~~~~~~~~~~~~~~~~~~
Validates Telegram WebApp initData (HMAC-SHA256 per official spec).
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

from botlite.config import BOT_TOKEN, WEBAPP_INIT_DATA_MAX_AGE


def validate_init_data(init_data: str) -> dict[str, Any] | None:
    """
    Validate the initData string sent by Telegram WebApp.

    Returns the parsed ``user`` dict on success, or ``None`` if the
    signature is missing, invalid, or the token is not configured.
    """
    if not init_data or not BOT_TOKEN:
        return None

    # Telegram signs the exact decoded key/value set. Reject duplicate keys
    # instead of silently accepting whichever value happens to win in a dict;
    # this prevents parser differentials between proxies and the application.
    pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    if not pairs:
        return None
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        return None
    params = dict(pairs)
    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

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

    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(params["auth_date"])
    except (KeyError, TypeError, ValueError):
        return None
    now = time.time()
    if auth_date > now + 60 or now - auth_date > WEBAPP_INIT_DATA_MAX_AGE:
        return None

    try:
        user = json.loads(params.get("user", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        return None
    return user
