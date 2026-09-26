"""Admin user listing: search and role/active filters with an accurate total.

The admin users table pages server-side, so the ``X-Total-Count`` header must
reflect the *filtered* count or the pager would offer phantom pages.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _admin(client, email):
    from tests.helpers import register_actor

    return await register_actor(client, email, "admin", full_name="Admin Users")


async def _student(client, email, name="Student One"):
    await client.post("/api/v1/auth/logout")
    from tests.helpers import register_actor

    return await register_actor(client, email, "student", full_name=name)


async def _login(client, email):
    await client.post("/api/v1/auth/logout")
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert r.status_code == 200, r.text


async def test_search_filters_by_email_or_name_and_reports_filtered_total(client):
    await _admin(client, "admin_search@ex.com")
    await _student(client, "zoe_filter@ex.com", "Zoe Filter")
    await _student(client, "sam_filter@ex.com", "Sam Filter")

    await _login(client, "admin_search@ex.com")
    r = await client.get("/api/v1/admin/users?q=zoe_filter")
    assert r.status_code == 200, r.text
    emails = [u["email"] for u in r.json()]
    assert "zoe_filter@ex.com" in emails
    assert "sam_filter@ex.com" not in emails
    # The header total reflects the filtered set, not the whole table.
    assert int(r.headers["X-Total-Count"]) == len(emails)


async def test_filter_by_role(client):
    await _admin(client, "admin_role@ex.com")
    await _student(client, "role_student@ex.com", "Role Student")

    await _login(client, "admin_role@ex.com")
    r = await client.get("/api/v1/admin/users?role=admin")
    assert r.status_code == 200, r.text
    for u in r.json():
        assert "admin" in u["roles"]
    assert "admin_role@ex.com" in [u["email"] for u in r.json()]

    r2 = await client.get("/api/v1/admin/users?role=student&q=role_student")
    assert r2.status_code == 200
    assert [u["email"] for u in r2.json()] == ["role_student@ex.com"]


async def test_filter_by_active_status(client):
    await _admin(client, "admin_active@ex.com")
    await _student(client, "active_yes@ex.com", "Active Yes")

    await _login(client, "admin_active@ex.com")
    # Deactivate the student.
    target = (await client.get("/api/v1/admin/users?q=active_yes")).json()[0]
    await client.patch(f"/api/v1/admin/users/{target['id']}/active", json={"is_active": False})

    inactive = await client.get("/api/v1/admin/users?is_active=false")
    assert inactive.status_code == 200
    assert "active_yes@ex.com" in [u["email"] for u in inactive.json()]

    active = await client.get("/api/v1/admin/users?is_active=true")
    assert "active_yes@ex.com" not in [u["email"] for u in active.json()]
