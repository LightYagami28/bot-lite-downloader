import asyncio

from aiohttp.test_utils import TestClient, TestServer

from botlite.webapp.server import create_app


async def _request(
    path: str, *, method: str = "GET", json: dict | None = None, headers: dict | None = None
):
    async with TestClient(TestServer(create_app())) as client:
        response = await client.request(method, path, json=json, headers=headers)
        return response.status, dict(response.headers), await response.text()


def test_status_endpoint_is_live_and_not_cacheable():
    status, headers, body = asyncio.run(_request("/api/status"))

    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert '"version"' in body
    assert '"active_downloads"' in body


def test_dashboard_script_is_served_same_origin_under_restrictive_script_csp():
    status, headers, body = asyncio.run(_request("/app.js"))

    script_policy = headers["Content-Security-Policy"].split("script-src", 1)[1].split(";", 1)[0]
    assert status == 200
    assert "javascript" in headers["Content-Type"]
    assert headers["Cache-Control"] == "no-store"
    assert "unsafe-inline" not in script_policy
    assert "Could not load status" in body


def test_dashboard_references_external_same_origin_script():
    status, headers, body = asyncio.run(_request("/"))

    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert '<script type="module" src="/app.js"></script>' in body
    assert '<script type="module">' not in body


def test_security_headers_are_applied_to_unauthorized_and_not_found_responses():
    for path in ("/api/me", "/api/stats", "/missing"):
        status, headers, _ = asyncio.run(_request(path))

        expected_status = 404 if path == "/missing" else 401
        assert status == expected_status
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in headers


def test_mutating_admin_endpoints_require_valid_telegram_authentication():
    for path in ("/api/ban", "/api/unban"):
        status, headers, _ = asyncio.run(_request(path, method="POST", json={"user_id": 123}))

        assert status == 401
        assert headers["Cache-Control"] == "no-store"


def test_api_me_authenticated(monkeypatch):
    monkeypatch.setattr(
        "botlite.webapp.server.validate_init_data",
        lambda data: (
            {"id": 100, "username": "admin", "first_name": "Admin"} if data == "auth" else None
        ),
    )
    monkeypatch.setattr("botlite.webapp.server.SUDO_USERS", [100])
    monkeypatch.setattr("botlite.webapp.server.db.is_banned", lambda uid: uid == 999)

    status, _, body = asyncio.run(_request("/api/me", headers={"X-Telegram-Init-Data": "auth"}))
    assert status == 200
    assert '"is_sudo": true' in body
    assert '"id": 100' in body
    assert '"banned": false' in body


def test_api_stats_sudo_and_forbidden(monkeypatch):
    def fake_validate(data):
        if data == "sudo":
            return {"id": 100}
        if data == "user":
            return {"id": 200}
        return None

    monkeypatch.setattr("botlite.webapp.server.validate_init_data", fake_validate)
    monkeypatch.setattr("botlite.webapp.server.SUDO_USERS", [100])
    monkeypatch.setattr(
        "botlite.webapp.server.db.get_stat", lambda name: 15 if name == "total_downloads" else 2
    )

    # Sudo user: 200 OK
    status, _, body = asyncio.run(_request("/api/stats", headers={"X-Telegram-Init-Data": "sudo"}))
    assert status == 200
    assert '"total_downloads": 15' in body

    # Non-sudo user: 403 Forbidden
    status_forbid, _, _ = asyncio.run(
        _request("/api/stats", headers={"X-Telegram-Init-Data": "user"})
    )
    assert status_forbid == 403


def test_api_ban_and_unban_actions(monkeypatch):
    banned = []
    unbanned = []
    monkeypatch.setattr(
        "botlite.webapp.server.validate_init_data",
        lambda data: {"id": 100} if data == "sudo" else None,
    )
    monkeypatch.setattr("botlite.webapp.server.SUDO_USERS", [100])
    monkeypatch.setattr("botlite.webapp.server.db.ban", lambda uid: banned.append(uid))
    monkeypatch.setattr("botlite.webapp.server.db.unban", lambda uid: unbanned.append(uid))

    headers = {"X-Telegram-Init-Data": "sudo"}

    # Successful ban
    status, _, body = asyncio.run(
        _request("/api/ban", method="POST", json={"user_id": 999}, headers=headers)
    )
    assert status == 200
    assert '"ok": true' in body
    assert banned == [999]

    # Successful unban
    status, _, body = asyncio.run(
        _request("/api/unban", method="POST", json={"user_id": 999}, headers=headers)
    )
    assert status == 200
    assert '"ok": true' in body
    assert unbanned == [999]

    # Bad requests: invalid user_id or negative
    for bad_json in ({"user_id": -5}, {"user_id": 0}, {"user_id": "not-int"}, {}):
        status, _, _ = asyncio.run(
            _request("/api/ban", method="POST", json=bad_json, headers=headers)
        )
        assert status == 400
        status_unban, _, _ = asyncio.run(
            _request("/api/unban", method="POST", json=bad_json, headers=headers)
        )
        assert status_unban == 400
