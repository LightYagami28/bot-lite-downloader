import asyncio

from aiohttp.test_utils import TestClient, TestServer

from botlite.webapp.server import create_app


async def _request(path: str, *, method: str = "GET", json: dict | None = None):
    async with TestClient(TestServer(create_app())) as client:
        response = await client.request(method, path, json=json)
        return response.status, dict(response.headers), await response.text()


def test_status_endpoint_is_live_and_not_cacheable():
    status, headers, body = asyncio.run(_request("/api/status"))

    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert '"version"' in body
    assert '"active_downloads"' in body


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
        status, headers, _ = asyncio.run(
            _request(path, method="POST", json={"user_id": 123})
        )

        assert status == 401
        assert headers["Cache-Control"] == "no-store"
