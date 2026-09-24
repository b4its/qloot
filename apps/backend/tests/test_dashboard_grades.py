"""Dashboard grade edit and delete controls (UIX-05)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Grade User")


async def test_grade_can_be_edited(client):
    await _register(client, "grade_edit@ex.com")
    created = await client.post(
        "/api/v1/career/grades",
        json={"subject": "Fisika", "grade": 70, "term": "2025/2026-genap"},
    )
    assert created.status_code == 200, created.text
    gid = created.json()["id"]

    edited = await client.put(f"/api/v1/career/grades/{gid}", json={"grade": 95})
    assert edited.status_code == 200, edited.text
    assert edited.json()["grade"] == 95
    assert edited.json()["subject"] == "Fisika"


async def test_grade_edit_is_owner_scoped(client):
    await _register(client, "grade_owner_a@ex.com")
    gid = (
        await client.post(
            "/api/v1/career/grades", json={"subject": "Kimia", "grade": 60}
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "grade_owner_b@ex.com")
    r = await client.put(f"/api/v1/career/grades/{gid}", json={"grade": 100})
    assert r.status_code == 404, r.text


async def test_grade_can_be_deleted(client):
    await _register(client, "grade_del@ex.com")
    gid = (
        await client.post(
            "/api/v1/career/grades", json={"subject": "Biologi", "grade": 80}
        )
    ).json()["id"]
    r = await client.delete(f"/api/v1/career/grades/{gid}")
    assert r.status_code == 200, r.text
    listing = await client.get("/api/v1/career/grades")
    assert all(g["id"] != gid for g in listing.json())
