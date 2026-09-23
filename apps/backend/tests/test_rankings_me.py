"""Ranking consistency: a user's own rank must match their global position.

Regression test for a bug where ``/rankings/me`` counted rivals using the *sum
of all attempts* (double-counting retries, including flagged) while
``/rankings/global`` ranked by best-per-exam. A retrying student was therefore
pushed down the personal board relative to their true global position.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name=email)


async def _make_exam(client, title="Ranking Exam"):
    exam = await client.post("/api/v1/exams", json={"title": title, "duration_minutes": 20})
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Apa itu energi?", "correct_answer": "kemampuan melakukan kerja"},
    )
    assert q.status_code == 201, q.text
    return exam_id, q.json()["id"]


async def _attempt(client, exam_id, qid, answer):
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert attempt.status_code == 201, attempt.text
    attempt_id = attempt.json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}",
        json={"answer_text": answer},
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    return attempt_id


async def test_rankings_me_rank_counts_rivals_by_best_per_exam(client):
    """A retrying student's rank must reflect the best-per-exam leaderboard."""
    await _register(client, "rk_teacher@ex.com", "teacher")
    exam_id, qid = await _make_exam(client)
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    # Student A retries the same exam twice.
    a = await _register(client, "rk_student_a@ex.com")
    await _attempt(client, exam_id, qid, "kemampuan melakukan kerja")
    await _attempt(client, exam_id, qid, "kemampuan melakukan kerja")
    me = (await client.get("/api/v1/rankings/me")).json()
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login",
        json={"email": "rk_student_a@ex.com", "password": "Password123!"},
    )
    board = (await client.get("/api/v1/rankings/global")).json()["entries"]
    entry = next(e for e in board if e["user_id"] == a["id"])

    # Total must be best-per-exam (one exam max = 10_000 bp), never doubled.
    assert me["total_score_bp"] == entry["score_bp"] <= 10_000

    # Rank uses the *same* 3-key ordering as the global board
    # (score desc, opc desc, id asc), so it must equal the caller's position in
    # that board. Deriving it from the board keeps the test order-independent.
    expected = next(i + 1 for i, e in enumerate(board) if e["user_id"] == a["id"])
    assert me["rank"] == expected
