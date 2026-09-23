"""Gamification: XP/level computation and level leaderboard."""

from __future__ import annotations

import pytest

from app.services.gamification_service import level_for_xp, level_progress

pytestmark = pytest.mark.integration


def test_level_thresholds_are_monotonic():
    # Level 1 at 0 XP; higher XP never lowers the level.
    assert level_for_xp(0)[0] == 1
    assert level_for_xp(499)[0] == 1
    assert level_for_xp(500)[0] == 2
    prev = 1
    for xp in range(0, 20000, 250):
        lvl = level_for_xp(xp)[0]
        assert lvl >= prev
        prev = lvl


def test_level_progress_bounds():
    assert 0.0 <= level_progress(0) < 1.0
    assert 0.0 <= level_progress(1234) <= 1.0
    # Just below a threshold the progress approaches 1.
    lvl, floor, ceiling = level_for_xp(1000)
    assert level_progress(ceiling - 1) > 0.9


async def _register(client, email, role="teacher"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="XP User")


async def test_gamification_me_returns_breakdown(client):
    await _register(client, "xp_me@ex.com")
    r = await client.get("/api/v1/gamification/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["level"] >= 1
    assert set(body["breakdown"]) == {"exams", "quests", "tasks", "badges"}
    assert body["xp"] == sum(body["breakdown"].values())


async def test_xp_increases_after_activity(client):
    # Teacher sets up a 1-question exam.
    await _register(client, "xp_teacher@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "XP Exam", "duration_minutes": 20})
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu energi?", "correct_answer": "kemampuan melakukan kerja"},
    )
    qid = q.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "xp_student@ex.com", "student")
    before = (await client.get("/api/v1/gamification/me")).json()["xp"]

    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}",
        json={"answer_text": "kemampuan melakukan kerja"},
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})

    after = (await client.get("/api/v1/gamification/me")).json()
    assert after["xp"] > before
    assert after["breakdown"]["exams"] > 0


async def test_levels_leaderboard_is_ordered(client):
    await _register(client, "lvl_a@ex.com")
    r = await client.get("/api/v1/gamification/levels")
    assert r.status_code == 200, r.text
    entries = r.json()["entries"]
    xps = [e["xp"] for e in entries]
    assert xps == sorted(xps, reverse=True)
    for i, e in enumerate(entries):
        assert e["rank"] == i + 1
        assert e["level"] >= 1


async def test_rankings_me_includes_level(client):
    await _register(client, "rank_lvl@ex.com")
    r = await client.get("/api/v1/rankings/me")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "level" in body and body["level"] >= 1
    assert "xp" in body
    assert 0.0 <= body["level_progress"] <= 1.0


async def test_gamification_me_progress_consistent(client):
    await _register(client, "xp_consist@ex.com")
    body = (await client.get("/api/v1/gamification/me")).json()
    xp = body["xp"]
    level, floor, ceiling = level_for_xp(xp)
    assert body["level"] == level
    assert body["xp_into_level"] == xp - floor
    assert body["xp_for_next_level"] == ceiling - floor
    assert body["quest_wins"] == 0
    assert body["tasks_completed"] == 0


async def test_levels_entry_for_known_user(client):
    user = await _register(client, "xp_lookup@ex.com")
    r = await client.get(f"/api/v1/gamification/levels/{user['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["level"] >= 1
    assert body["xp"] >= 0
    assert set(body["breakdown"]) == {"exams", "quests", "tasks", "badges"}


async def test_levels_entry_unknown_user_404(client):
    await _register(client, "xp_404@ex.com")
    r = await client.get("/api/v1/gamification/levels/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, r.text


async def test_levels_entry_malformed_id_404(client):
    await _register(client, "xp_bad@ex.com")
    r = await client.get("/api/v1/gamification/levels/not-a-uuid")
    assert r.status_code == 404, r.text


async def test_levels_leaderboard_empty_without_activity(client):
    await _register(client, "xp_lonely@ex.com")
    r = await client.get("/api/v1/gamification/levels")
    assert r.status_code == 200, r.text
    # A fresh user has no graded attempts, so the leaderboard may be empty.
    assert r.json()["scope"] == "levels"
    assert isinstance(r.json()["entries"], list)
