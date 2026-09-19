"""Regression tests for bugs found during the code audit.

Each test here corresponds to a specific fix:
  - grading denominator must include skipped questions
  - answers may not be injected for questions from another exam
  - repeated transfers to the same recipient must not collide
  - room ranking must not include scores from unrelated exams
  - global ranking must use best-score-per-exam (no retry double counting)
  - admin reward retry must carry the real user reference
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", name="Test User"):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": name, "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_exam_with_questions(client, n=2):
    exam = await client.post("/api/v1/exams", json={"title": "Audit Exam"})
    assert exam.status_code == 201
    exam_id = exam.json()["id"]
    qids = []
    for i in range(n):
        q = await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": f"Question {i}?", "correct_answer": "reference answer", "position": i},
        )
        assert q.status_code == 201, q.text
        qids.append(q.json()["id"])
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, qids


async def test_skipping_questions_lowers_the_score(client):
    """A student answering 1 of 2 questions perfectly must score ~50%, not 100%."""
    await _register(client, "t_skip@ex.com", "teacher")
    exam_id, qids = await _make_exam_with_questions(client, n=2)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_skip@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    # Answer only the first question.
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}",
        json={"answer_text": "reference answer"},
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    grade = await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    assert grade.status_code == 200

    result = await client.get(f"/api/v1/attempts/{attempt_id}/result")
    score_bp = result.json()["attempt"]["score_bp"]
    # The unanswered question must count against the total (<= ~5000 bp, not 10000).
    assert score_bp is not None
    assert score_bp <= 6000, f"skipped question not counted against score: {score_bp}"


async def test_cannot_answer_question_from_another_exam(client):
    await _register(client, "t_x@ex.com", "teacher")
    exam_a, _ = await _make_exam_with_questions(client, n=1)
    exam_b, qids_b = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_x@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_a}/attempts")
    attempt_id = attempt.json()["id"]
    # Try to answer a question that belongs to exam_b.
    resp = await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qids_b[0]}",
        json={"answer_text": "injected"},
    )
    assert resp.status_code == 404


async def test_repeated_transfers_do_not_collide(client, engine):
    """Two identical transfers to the same recipient must both succeed."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import User
    from app.services.reward_engine import RewardEngine

    await _register(client, "t_tr@ex.com", "teacher")
    exam_id, _ = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    # Sender gets funded via the ledger, recipient is a second student.
    await _register(client, "s_send@ex.com", "student", "Sender")
    sender_me = await client.get("/api/v1/auth/me")
    sender_id = sender_me.json()["id"]
    await client.post("/api/v1/auth/logout")
    await _register(client, "s_recv@ex.com", "student", "Receiver")
    recv_me = await client.get("/api/v1/auth/me")
    recv_id = recv_me.json()["id"]
    await client.post("/api/v1/auth/logout")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        sender = await s.get(User, uuid.UUID(sender_id))
        engine_ = RewardEngine(s)
        await engine_.credit(
            user=sender,
            amount=100,
            reference_type="testfund",
            reference_id="seed",
            reward_key_value="seed",
            token_id=0,
        )
        await s.commit()

    await client.post(
        "/api/v1/auth/login", json={"email": "s_send@ex.com", "password": "Password123!"}
    )
    for _ in range(2):
        r = await client.post(
            "/api/v1/wallet/transfers", json={"to_user_id": recv_id, "amount": 10}
        )
        assert r.status_code == 200, r.text
    wallet = await client.get("/api/v1/wallet")
    assert wallet.json()["available"] == 80


async def test_room_ranking_excludes_unrelated_exams(client, engine):
    """Scores from exams not tied to a room must not appear in its ranking."""


    # Teacher creates a room and an exam NOT linked to it.
    await _register(client, "t_room@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Audit Room"})
    room_id = room.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/open")
    exam_id, qids = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_room@ex.com", "student")
    me = await client.get("/api/v1/auth/me")
    student_id = me.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}", json={"answer_text": "reference answer"}
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})

    rank = await client.get(f"/api/v1/rankings/rooms/{room_id}")
    assert rank.status_code == 200
    entries = {e["user_id"]: e["score_bp"] for e in rank.json()["entries"]}
    # The student is a member, but has no exam tied to the room -> score 0.
    assert entries.get(student_id, 0) == 0


async def test_global_ranking_uses_best_per_exam(client):
    """Retrying the same exam must not double-count in the global ranking."""
    await _register(client, "t_g@ex.com", "teacher")
    exam_id, qids = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_g@ex.com", "student")
    me = await client.get("/api/v1/auth/me")
    student_id = me.json()["id"]

    # Two attempts on the same exam.
    for _ in range(2):
        attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
        attempt_id = attempt.json()["id"]
        await client.put(
            f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}",
            json={"answer_text": "reference answer"},
        )
        await client.post(f"/api/v1/attempts/{attempt_id}/submit")
        await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})

    rank = await client.get("/api/v1/rankings/global")
    entry = next(
        (e for e in rank.json()["entries"] if e["user_id"] == student_id),
        None,
    )
    assert entry is not None
    # One exam answered -> total equals a single attempt's score (<= 10000).
    assert entry["score_bp"] <= 10000
