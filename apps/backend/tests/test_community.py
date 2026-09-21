"""Community (social feed) — posts, likes, comments, topics, stats."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Feed User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_post_list_like_comment(client):
    await _register(client, "feed_a@ex.com")
    created = await client.post(
        "/api/v1/community/posts",
        json={"body": "Halo komunitas QLoot!", "topic": "Umum"},
    )
    assert created.status_code == 201, created.text
    post = created.json()
    assert post["body"] == "Halo komunitas QLoot!"
    assert post["like_count"] == 0
    assert post["liked_by_me"] is False
    assert post["author_name"] == "Feed User"
    post_id = post["id"]

    # Appears in the feed.
    feed = await client.get("/api/v1/community/posts")
    assert feed.status_code == 200
    assert any(p["id"] == post_id for p in feed.json())

    # Like toggles on/off.
    liked = await client.post(f"/api/v1/community/posts/{post_id}/like")
    assert liked.status_code == 200
    assert liked.json()["like_count"] == 1
    assert liked.json()["liked_by_me"] is True
    unliked = await client.post(f"/api/v1/community/posts/{post_id}/like")
    assert unliked.json()["like_count"] == 0
    assert unliked.json()["liked_by_me"] is False

    # Comment.
    c = await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"body": "Mantap!"})
    assert c.status_code == 201, c.text
    detail = await client.get(f"/api/v1/community/posts/{post_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["comment_count"] == 1
    assert len(body["comments"]) == 1
    assert body["comments"][0]["body"] == "Mantap!"


async def test_like_is_per_user(client):
    await _register(client, "feed_owner@ex.com")
    post = await client.post("/api/v1/community/posts", json={"body": "Post untuk like"})
    post_id = post.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "feed_other@ex.com")
    like = await client.post(f"/api/v1/community/posts/{post_id}/like")
    assert like.json()["like_count"] == 1


async def test_topics_and_stats(client):
    await _register(client, "feed_topic@ex.com")
    await client.post("/api/v1/community/posts", json={"body": "Diskusi AI", "topic": "Data & AI"})
    topics = await client.get("/api/v1/community/topics")
    assert topics.status_code == 200
    assert any(t["name"] == "Data & AI" and t["posts"] >= 1 for t in topics.json())

    stats = await client.get("/api/v1/community/stats")
    assert stats.status_code == 200
    assert stats.json()["posts"] >= 1
    assert stats.json()["members"] >= 1


async def test_delete_others_post_forbidden(client):
    await _register(client, "feed_author@ex.com")
    post = await client.post("/api/v1/community/posts", json={"body": "Punya saya"})
    post_id = post.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "feed_intruder@ex.com")
    r = await client.delete(f"/api/v1/community/posts/{post_id}")
    assert r.status_code == 403
