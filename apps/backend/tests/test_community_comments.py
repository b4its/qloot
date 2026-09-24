"""Community comment editing and nested replies (COMM-02)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Thread User")


async def _make_post(client) -> str:
    r = await client.post("/api/v1/community/posts", json={"body": "Pos diskusi", "topic": "Umum"})
    return r.json()["id"]


async def test_nested_reply_is_stored_under_its_parent(client):
    await _register(client, "th_author@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "th_replier@ex.com")
    root = (
        await client.post(
            f"/api/v1/community/posts/{post_id}/comments", json={"body": "Komentar induk"}
        )
    ).json()
    reply = await client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"body": "Balasan", "parent_id": root["id"]},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["parent_id"] == root["id"]

    listing = await client.get(f"/api/v1/community/posts/{post_id}/comments")
    assert any(c["parent_id"] == root["id"] for c in listing.json())


async def test_reply_depth_is_bounded(client):
    await _register(client, "th_author2@ex.com")
    post_id = await _make_post(client)
    await client.post("/api/v1/auth/logout")
    await _register(client, "th_replier2@ex.com")

    parent_id = None
    # Build a chain up to the max depth (3), which should succeed.
    for i in range(3):
        r = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            json={"body": f"level {i}", "parent_id": parent_id},
        )
        assert r.status_code == 201, r.text
        parent_id = r.json()["id"]
    # One more (depth 4) must be rejected.
    deep = await client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        json={"body": "terlalu dalam", "parent_id": parent_id},
    )
    assert deep.status_code == 422, deep.text


async def test_author_can_edit_their_comment_and_it_is_marked(client):
    await _register(client, "th_editor@ex.com")
    post_id = await _make_post(client)
    cid = (
        await client.post(
            f"/api/v1/community/posts/{post_id}/comments", json={"body": "versi awal"}
        )
    ).json()["id"]

    edited = await client.patch(f"/api/v1/community/comments/{cid}", json={"body": "versi baru"})
    assert edited.status_code == 200, edited.text
    assert edited.json()["body"] == "versi baru"
    assert edited.json()["edited_at"] is not None


async def test_other_users_cannot_edit_a_comment(client):
    await _register(client, "th_author4@ex.com")
    post_id = await _make_post(client)
    cid = (
        await client.post(
            f"/api/v1/community/posts/{post_id}/comments", json={"body": "milik author"}
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "th_other4@ex.com")
    r = await client.patch(f"/api/v1/community/comments/{cid}", json={"body": "dibajak"})
    assert r.status_code == 403, r.text


async def test_comments_support_offset_pagination(client):
    await _register(client, "th_author5@ex.com")
    post_id = await _make_post(client)
    for i in range(5):
        await client.post(
            f"/api/v1/community/posts/{post_id}/comments", json={"body": f"k{i}"}
        )
    page1 = await client.get(f"/api/v1/community/posts/{post_id}/comments?limit=2&offset=0")
    page2 = await client.get(f"/api/v1/community/posts/{post_id}/comments?limit=2&offset=2")
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    assert {c["id"] for c in page1.json()}.isdisjoint({c["id"] for c in page2.json()})
