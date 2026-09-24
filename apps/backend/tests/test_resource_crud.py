"""Resource library search + teacher CRUD tests (CARE-07)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Resource User")


async def test_resource_search_filters_by_query(client):
    await _register(client, f"res_search_{uuid.uuid4().hex[:6]}@ex.com")
    # Make sure the catalog is seeded.
    all_items = await client.get("/api/v1/career/resources")
    assert all_items.status_code == 200
    assert len(all_items.json()) >= 1

    first = all_items.json()[0]
    term = first["title"].split()[0]
    filtered = await client.get(f"/api/v1/career/resources?q={term}")
    assert filtered.status_code == 200, filtered.text
    assert all(
        term.lower() in (i["title"] + (i["description"] or "")).lower()
        for i in filtered.json()
    )


async def test_teacher_can_create_update_delete_resource(client):
    await _register(client, f"res_teacher_{uuid.uuid4().hex[:6]}@ex.com", "teacher")
    code = f"res_test_{uuid.uuid4().hex[:10]}"
    create = await client.post(
        "/api/v1/career/resources",
        json={
            "code": code,
            "category": "course",
            "title": "Kursus Uji",
            "description": "Deskripsi uji",
            "is_free": True,
            "tags": ["matematika"],
        },
    )
    assert create.status_code == 201, create.text

    # Duplicate code -> 409.
    dup = await client.post(
        "/api/v1/career/resources",
        json={"code": code, "category": "course", "title": "Lagi"},
    )
    assert dup.status_code == 409

    upd = await client.patch(
        f"/api/v1/career/resources/{code}", json={"title": "Kursus Uji v2"}
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["title"] == "Kursus Uji v2"

    deleted = await client.delete(f"/api/v1/career/resources/{code}")
    assert deleted.status_code == 200, deleted.text


async def test_students_cannot_mutate_resources(client):
    await _register(client, f"res_student_{uuid.uuid4().hex[:6]}@ex.com", "student")
    create = await client.post(
        "/api/v1/career/resources",
        json={
            "code": f"res_nope_{uuid.uuid4().hex[:8]}",
            "category": "course",
            "title": "Tidak boleh",
        },
    )
    assert create.status_code == 403, create.text


async def test_resource_create_validates_category(client):
    await _register(client, f"res_teacher2_{uuid.uuid4().hex[:6]}@ex.com", "teacher")
    bad = await client.post(
        "/api/v1/career/resources",
        json={"code": "res_bad", "category": "nonsense", "title": "Salah kategori"},
    )
    assert bad.status_code == 422, bad.text

