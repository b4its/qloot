"""Community post free-text search (``q``).

The feed is browsed by topic + sort; ``q`` adds a search over the post body and
the author's display name so a member can find a specific discussion.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, name="Community User"):
    from tests.helpers import register_actor

    return await register_actor(client, email, "student", full_name=name)


async def _post(client, body, topic="Umum"):
    r = await client.post("/api/v1/community/posts", json={"body": body, "topic": topic})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_search_filters_posts_by_body(client):
    await _register(client, "search_body@ex.com")
    await _post(client, "Tips belajar matematika cepat")
    await _post(client, "Resep nasi goreng enak")

    r = await client.get("/api/v1/community/posts?q=matematika")
    assert r.status_code == 200, r.text
    bodies = [p["body"] for p in r.json()]
    assert any("matematika" in b.lower() for b in bodies)
    assert all("nasi goreng" not in b.lower() for b in bodies)


async def test_search_matches_author_name(client):
    await _register(client, "zonk@ex.com", name="Zonk Spesial")
    await _post(client, "Postingan biasa")
    await client.post("/api/v1/auth/logout")

    await _register(client, "reader@ex.com", name="Reader")
    r = await client.get("/api/v1/community/posts?q=zonk")
    assert r.status_code == 200, r.text
    # The post authored by "Zonk Spesial" is returned via the name match.
    assert any(p["body"] == "Postingan biasa" for p in r.json())


async def test_search_with_no_match_is_empty(client):
    await _register(client, "search_empty@ex.com")
    await _post(client, "Halo dunia")
    r = await client.get("/api/v1/community/posts?q=zzz_no_such_text_zzz")
    assert r.status_code == 200, r.text
    assert r.json() == []
