"""Admin audit-log free-text search (``q``).

The audit trail is trace-only, so an operator needs to find one event by a
fragment (action, entity, actor, or request id) without knowing its exact slug.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _admin(client, email="admin_audit@ex.com"):
    from tests.helpers import register_actor

    return await register_actor(client, email, "admin", full_name="Admin Audit")


async def test_search_filters_by_action_fragment_and_reports_total(client):
    await _admin(client)
    # A login produces an auth.login audit row.
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": "admin_audit@ex.com", "password": "Password123!"}
    )

    r = await client.get("/api/v1/admin/audit-logs?q=login&limit=50")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 1
    # Every returned row's action contains "login".
    assert all("login" in row["action"].lower() for row in rows)
    assert int(r.headers["X-Total-Count"]) == len(rows)


async def test_search_that_matches_nothing_is_empty(client):
    await _admin(client, "admin_audit_empty@ex.com")
    r = await client.get("/api/v1/admin/audit-logs?q=zzz_no_such_action_zzz")
    assert r.status_code == 200, r.text
    assert r.json() == []
    assert int(r.headers["X-Total-Count"]) == 0
