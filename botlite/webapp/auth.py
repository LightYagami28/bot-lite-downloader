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

    params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
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
    if auth_date > time.time() + 60 or time.time() - auth_date > WEBAPP_INIT_DATA_MAX_AGE:
        return None

    try:
        return json.loads(params.get("user", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}
