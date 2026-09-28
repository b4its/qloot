"""Self-service data export (W5 data portability)."""

from __future__ import annotations

import json

import pytest

from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def test_export_returns_only_own_data(client):
    await register_actor(client, "export_me@ex.com", "student", full_name="Export Me")

    resp = await client.get("/api/v1/auth/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers.get("content-disposition", "")

    body = json.loads(resp.text)
    assert body["schema_version"] == 1
    assert body["profile"]["email"] == "export_me@ex.com"
    assert body["profile"]["full_name"] == "Export Me"
    # Sensitive fields must never be exported.
    dumped = resp.text.lower()
    assert "password" not in dumped
    assert "token_hash" not in dumped
    # Data sections exist even when empty.
    for section in (
        "learning_progress",
        "exam_attempts",
        "badges",
        "certificates",
    ):
        assert section in body


async def test_export_requires_authentication(client):
    # Fresh client with no session cookie must be rejected.
    resp = await client.get("/api/v1/auth/export")
    assert resp.status_code in (401, 403)
