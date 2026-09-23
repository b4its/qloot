"""Security middleware coverage: CSRF (C03) and CORS/headers (C07)."""

from __future__ import annotations

import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


@pytest.fixture
def enable_csrf(monkeypatch):
    monkeypatch.setattr(settings, "csrf_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")
    yield


async def test_unsafe_method_without_csrf_is_rejected(client, enable_csrf):
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "x@ex.com", "password": "whatever"}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "csrf_failed"


async def test_safe_get_issues_csrf_cookie(client, enable_csrf):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.cookies.get(settings.csrf_cookie_name)
    # The token is readable by JS (not HttpOnly) so the client can echo it.
    set_cookie = resp.headers.get("set-cookie", "")
    assert settings.csrf_cookie_name in set_cookie
    assert "httponly" not in set_cookie.lower()


async def test_unsafe_method_with_matching_csrf_passes(client, enable_csrf):
    # Prime the CSRF cookie on a safe request.
    await client.get("/api/v1/health/live")
    token = client.cookies.get(settings.csrf_cookie_name)
    assert token
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@ex.com", "password": "nope"},
        headers={settings.csrf_header_name: token},
    )
    # Not a CSRF failure — the request reached the auth handler (401 invalid creds).
    assert resp.status_code == 401, resp.text


async def test_mismatched_csrf_token_is_rejected(client, enable_csrf):
    await client.get("/api/v1/health/live")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@ex.com", "password": "nope"},
        headers={settings.csrf_header_name: "not-the-cookie"},
    )
    assert resp.status_code == 403
