"""Readiness probe tests (AUTH-06).

`/ready` must probe every critical dependency (database, Redis, object
storage) and return 503 when any of them is down, so an orchestrator does not
route traffic to a half-broken pod. `/live` stays a cheap liveness check.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def test_live_is_cheap_and_ok(client):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_ready_reports_each_configured_dependency(client):
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ok"
    # Database and storage are always probed; Redis only when enabled.
    assert body["checks"]["database"] == "ok"
    assert "storage" in body["checks"]


async def test_ready_is_degraded_when_redis_down(client, monkeypatch):
    """When the Redis probe is enabled and Redis is unreachable, /ready is 503."""
    from app.api.v1 import health

    monkeypatch.setattr(health.settings, "readiness_check_redis", True)

    async def _down() -> str:
        return "error: ConnectionError"

    monkeypatch.setattr(health, "_check_redis", _down)
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"].startswith("error")


async def test_ready_is_degraded_when_storage_down(client, monkeypatch):
    from app.api.v1 import health

    monkeypatch.setattr(health, "_check_storage", lambda: "error: unreachable")
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 503, resp.text
    assert resp.json()["checks"]["storage"].startswith("error")


async def test_ready_is_degraded_when_database_down(client, monkeypatch):
    from app.api.v1 import health

    async def _down() -> str:
        return "error: OperationalError"

    monkeypatch.setattr(health, "_check_database", _down)
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 503, resp.text
    assert resp.json()["checks"]["database"].startswith("error")
