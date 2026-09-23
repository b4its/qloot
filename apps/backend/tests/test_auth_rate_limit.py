"""Rate limiting on sensitive auth/AI endpoints (AUTH-01, CARE-04).

The limiter is a no-op under ``app_env=test``; these tests flip it on and use
the in-process fallback (Redis is not connected under ASGITransport), then
restore the settings afterwards.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.middleware import rate_limit as rl

pytestmark = pytest.mark.integration


@pytest.fixture
def enable_rate_limit(monkeypatch):
    """Turn the limiter on with tiny windows and clear local counters."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "rate_limit_login", 3)
    monkeypatch.setattr(settings, "rate_limit_register", 2)
    monkeypatch.setattr(settings, "rate_limit_password_reset", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    rl._local.clear()  # noqa: SLF001
    yield
    rl._local.clear()  # noqa: SLF001


async def test_login_is_rate_limited(client, enable_rate_limit):
    # A fresh test client is reused; fire bad logins past the limit.
    codes = []
    for _ in range(5):
        r = await client.post(
            "/api/v1/auth/login", json={"email": "nobody@ex.com", "password": "nope"}
        )
        codes.append(r.status_code)
    assert 429 in codes, codes
    throttled = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@ex.com", "password": "nope"}
    )
    assert throttled.status_code == 429
    assert throttled.headers.get("Retry-After")
    assert throttled.json()["error"]["code"] == "rate_limited"


async def test_register_is_rate_limited(client, enable_rate_limit):
    codes = []
    for i in range(4):
        r = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"rl_reg_{i}@ex.com",
                "full_name": "RL User",
                "password": "Password123!",
            },
        )
        codes.append(r.status_code)
        if r.status_code == 201:
            await client.post("/api/v1/auth/logout")
    assert 429 in codes, codes


async def test_forgot_password_is_rate_limited(client, enable_rate_limit):
    codes = []
    for _ in range(4):
        r = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@ex.com"}
        )
        codes.append(r.status_code)
    assert 429 in codes, codes
    assert r.headers.get("Retry-After")


async def test_limiter_falls_back_without_redis(client, enable_rate_limit, monkeypatch):
    """Redis down must not turn throttling into a 500."""
    # Force the redis lookup to report "unavailable".
    async def _no_redis():
        return None

    monkeypatch.setattr(rl, "_redis", _no_redis)
    r = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@ex.com", "password": "nope"}
    )
    assert r.status_code in (401, 429)  # never 500
