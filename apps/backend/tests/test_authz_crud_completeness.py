"""Regression tests for the 'complete every feature' pass, round 3.

Covers authorization/visibility + CRUD-symmetry gaps:
  - draft quests are not readable by id (404), incl. winners + quest ranking
  - a private room's ranking 404s for non-members
  - a quest cannot reference an exam the caller does not own
  - community comments can be deleted (author/admin only)
  - career grades can be deleted (owner only)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="teacher"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Round3 User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_published_exam(client, title="R3 Exam"):
    exam = await client.post("/api/v1/exams", json={"title": title, "duration_minutes": 10})
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id


# --- quest visibility -----------------------------------------------------
async def test_draft_quest_is_hidden_from_other_users(client):
    await _register(client, "q3_owner@ex.com")
    quest = await client.post(
        "/api/v1/quests",
        json={
            "title": "Draft Quest",
            "top_n_winners": 1,
            "rules": [{"rank": 1, "reward_amount": 5}],
        },
    )
    assert quest.status_code == 201, quest.text
    quest_id = quest.json()["id"]
    # Owner can read their own draft.
    assert (await client.get(f"/api/v1/quests/{quest_id}")).status_code == 200
    await client.post("/api/v1/auth/logout")

    # A student must not see a draft quest by id.
    await _register(client, "q3_student@ex.com", "student")
    assert (await client.get(f"/api/v1/quests/{quest_id}")).status_code == 404
    assert (await client.get(f"/api/v1/quests/{quest_id}/winners")).status_code == 404
    assert (await client.get(f"/api/v1/rankings/quests/{quest_id}")).status_code == 404


async def test_another_teacher_cannot_read_a_foreign_draft_quest(client):
    await _register(client, "q3_owner2@ex.com")
    quest_id = (
        await client.post(
            "/api/v1/quests",
            json={
                "title": "Private Draft",
                "top_n_winners": 1,
                "rules": [{"rank": 1, "reward_amount": 1}],
            },
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "q3_teacher2@ex.com")
    assert (await client.get(f"/api/v1/quests/{quest_id}")).status_code == 404


async def test_open_quest_is_visible_to_students(client):
    await _register(client, "q3_owner3@ex.com")
    exam_id = await _make_published_exam(client, "Q3 Open Exam")
    quest_id = (
        await client.post(
            "/api/v1/quests",
            json={
                "title": "Open Quest",
                "exam_id": exam_id,
                "top_n_winners": 1,
                "rules": [{"rank": 1, "reward_amount": 5}],
            },
        )
    ).json()["id"]
    assert (await client.post(f"/api/v1/quests/{quest_id}/publish")).status_code == 200
    await client.post("/api/v1/auth/logout")

    await _register(client, "q3_student2@ex.com", "student")
    assert (await client.get(f"/api/v1/quests/{quest_id}")).status_code == 200


async def test_quest_cannot_reference_another_teachers_exam(client):
    await _register(client, "q3_exam_owner@ex.com")
    exam_id = await _make_published_exam(client, "Foreign Exam")
    await client.post("/api/v1/auth/logout")

    # A different teacher tries to attach their quest to that exam.
    await _register(client, "q3_other_teacher@ex.com")
    resp = await client.post(
        "/api/v1/quests",
        json={
            "title": "Hijack Quest",
            "exam_id": exam_id,
            "top_n_winners": 1,
            "rules": [{"rank": 1, "reward_amount": 1}],
        },
    )
    assert resp.status_code == 403, resp.text


# --- room ranking visibility ---------------------------------------------
async def test_private_room_ranking_hidden_from_non_members(client):
    await _register(client, "r3_owner@ex.com")
    room_id = (
        await client.post("/api/v1/rooms", json={"name": "Priv", "is_public": False})
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "r3_stranger@ex.com", "student")
    denied = await client.get(f"/api/v1/rankings/rooms/{room_id}")
    assert denied.status_code == 404, denied.text


async def test_public_room_ranking_visible(client):
    await _register(client, "r3_owner2@ex.com")
    room_id = (await client.post("/api/v1/rooms", json={"name": "Pub", "is_public": True})).json()[
        "id"
    ]
    await client.post("/api/v1/auth/logout")

    await _register(client, "r3_viewer@ex.com", "student")
    ok = await client.get(f"/api/v1/rankings/rooms/{room_id}")
    assert ok.status_code == 200, ok.text


# --- community comment delete --------------------------------------------
async def test_delete_own_comment(client):
    await _register(client, "c3_author@ex.com", "student")
    post_id = (
        await client.post("/api/v1/community/posts", json={"body": "Halo", "topic": "Umum"})
    ).json()["id"]
    comment = await client.post(
        f"/api/v1/community/posts/{post_id}/comments", json={"body": "Komentar saya"}
    )
    assert comment.status_code == 201, comment.text
    comment_id = comment.json()["id"]

    dele = await client.delete(f"/api/v1/community/comments/{comment_id}")
    assert dele.status_code == 200, dele.text
    # The post's comment_count is decremented back to 0.
    detail = await client.get(f"/api/v1/community/posts/{post_id}")
    assert detail.json()["comment_count"] == 0


async def test_cannot_delete_another_users_comment(client):
    await _register(client, "c3_author2@ex.com", "student")
    post_id = (
        await client.post("/api/v1/community/posts", json={"body": "Hi", "topic": "Umum"})
    ).json()["id"]
    comment_id = (
        await client.post(f"/api/v1/community/posts/{post_id}/comments", json={"body": "Milik A"})
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "c3_other@ex.com", "student")
    denied = await client.delete(f"/api/v1/community/comments/{comment_id}")
    assert denied.status_code == 403, denied.text


# --- career grade delete --------------------------------------------------
async def test_delete_own_grade(client):
    await _register(client, "g3_student@ex.com", "student")
    up = await client.post(
        "/api/v1/career/grades",
        json={"subject": "Matematika", "grade": 80, "term": "2025/2026-genap"},
    )
    assert up.status_code == 200, up.text
    grade_id = up.json()["id"]
    assert grade_id is not None

    dele = await client.delete(f"/api/v1/career/grades/{grade_id}")
    assert dele.status_code == 200, dele.text
    grades = await client.get("/api/v1/career/grades")
    assert all(g["subject"] != "Matematika" for g in grades.json())


async def test_cannot_delete_another_users_grade(client):
    await _register(client, "g3_owner@ex.com", "student")
    grade_id = (
        await client.post(
            "/api/v1/career/grades", json={"subject": "Fisika", "grade": 90, "term": "t"}
        )
    ).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "g3_other@ex.com", "student")
    denied = await client.delete(f"/api/v1/career/grades/{grade_id}")
    assert denied.status_code == 404, denied.text
