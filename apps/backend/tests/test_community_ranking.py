"""Community hot/top feed ranking (COMM-05)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Rank User")


async def test_invalid_sort_is_rejected(client):
    await _register(client, f"rank_bad_{uuid.uuid4().hex[:6]}@ex.com")
    r = await client.get("/api/v1/community/posts?sort=nonsense")
    assert r.status_code == 422, r.text


async def test_top_sorts_by_engagement(client):
    await _register(client, f"rank_author_{uuid.uuid4().hex[:6]}@ex.com")
    low = (
        await client.post(
            "/api/v1/community/posts", json={"body": "pos sepi", "topic": "umum_rank_test"}
        )
    ).json()["id"]
    high = (
        await client.post(
            "/api/v1/community/posts", json={"body": "pos ramai", "topic": "umum_rank_test"}
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    # A different user likes the "high" post twice via two accounts.
    for _ in range(2):
        await _register(client, f"rank_liker_{uuid.uuid4().hex[:6]}@ex.com")
        await client.post(f"/api/v1/community/posts/{high}/like")
        await client.post("/api/v1/auth/logout")

    await _register(client, f"rank_viewer_{uuid.uuid4().hex[:6]}@ex.com")
    r = await client.get("/api/v1/community/posts?sort=top&limit=50&topic=umum_rank_test")
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()]
    assert ids.index(high) < ids.index(low)


async def test_hot_ranking_is_deterministic(client):
    await _register(client, f"rank_author2_{uuid.uuid4().hex[:6]}@ex.com")
    for i in range(3):
        await client.post(
            "/api/v1/community/posts", json={"body": f"pos {i}", "topic": "hot_rank_test"}
        )
    first = await client.get("/api/v1/community/posts?sort=hot&limit=20&topic=hot_rank_test")
    second = await client.get("/api/v1/community/posts?sort=hot&limit=20&topic=hot_rank_test")
    assert [p["id"] for p in first.json()] == [p["id"] for p in second.json()]


async def test_default_sort_is_recency(client):
    await _register(client, f"rank_author3_{uuid.uuid4().hex[:6]}@ex.com")
    older = (
        await client.post(
            "/api/v1/community/posts", json={"body": "dulu", "topic": "new_rank_test"}
        )
    ).json()["id"]
    newer = (
        await client.post(
            "/api/v1/community/posts", json={"body": "sekarang", "topic": "new_rank_test"}
        )
    ).json()["id"]
    r = await client.get("/api/v1/community/posts?topic=new_rank_test")
    ids = [p["id"] for p in r.json()]
    assert ids.index(newer) < ids.index(older)
