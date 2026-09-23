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


# --- security headers (C07) ------------------------------------------------
async def test_security_headers_present(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    # CSP is only for non-docs paths; live endpoint is not exempt.
    assert "Content-Security-Policy" in resp.headers


async def test_hsts_only_in_production(client, monkeypatch):
    resp = await client.get("/api/v1/health/live")
    assert "Strict-Transport-Security" not in resp.headers
    monkeypatch.setattr(settings, "app_env", "production")
    resp2 = await client.get("/api/v1/health/live")
    assert "Strict-Transport-Security" in resp2.headers


# --- CORS (C07) ------------------------------------------------------------
async def test_cors_allows_configured_origin_with_credentials(client):
    origin = settings.cors_origins[0]
    resp = await client.get("/api/v1/health/live", headers={"Origin": origin})
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-credentials") == "true"


async def test_cors_rejects_non_allowlisted_origin(client):
    resp = await client.get(
        "/api/v1/health/live", headers={"Origin": "https://evil.example"}
    )
    # No ACAO header is echoed for a disallowed origin.
    assert "access-control-allow-origin" not in resp.headers

