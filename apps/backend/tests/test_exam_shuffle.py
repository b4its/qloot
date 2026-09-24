"""Per-attempt deterministic question/option shuffle (C21)."""

from __future__ import annotations

import pytest

from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def _make_shuffled_exam(client, *, questions=True, options=True) -> tuple[str, list[str]]:
    exam = await client.post(
        "/api/v1/exams",
        json={
            "title": "Shuffle Exam",
            "duration_minutes": 30,
            "shuffle_questions": questions,
            "shuffle_options": options,
            "max_attempts": 10,
        },
    )
    exam_id = exam.json()["id"]
    qids = []
    for i in range(4):
        q = await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={
                "prompt": f"Pertanyaan nomor {i}?",
                "qtype": "multiple_choice",
                "position": i,
                "options": [
                    {"text": f"Benar {i}", "is_correct": True},
                    {"text": f"Salah {i}a", "is_correct": False},
                    {"text": f"Salah {i}b", "is_correct": False},
                    {"text": f"Salah {i}c", "is_correct": False},
                ],
            },
        )
        assert q.status_code == 201, q.text
        qids.append(q.json()["id"])
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, qids


async def _attempt_question_order(client, attempt_id) -> list[str]:
    rows = await client.get(f"/api/v1/attempts/{attempt_id}/questions")
    assert rows.status_code == 200, rows.text
    return [r["id"] for r in rows.json()]


async def _option_order(client, attempt_id, question_id) -> list[str]:
    rows = await client.get(f"/api/v1/attempts/{attempt_id}/questions")
    for r in rows.json():
        if r["id"] == question_id:
            return [o["label"] for o in r["options"]]
    raise AssertionError("question not found")


async def test_shuffle_is_stable_per_attempt_and_differs_between_attempts(client):
    await register_actor(client, "shuf_teacher@ex.com", "teacher")
    exam_id, _ = await _make_shuffled_exam(client)
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "shuf_student@ex.com", "student")
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]

    order_a1_first = await _attempt_question_order(client, a1)
    order_a1_second = await _attempt_question_order(client, a1)
    # Same attempt reloaded -> identical order.
    assert order_a1_first == order_a1_second

    # Across several attempts the ordering must vary for at least one pair (a
    # fixed order for everyone is the bug this feature prevents).
    orders = {tuple(order_a1_first)}
    for _ in range(6):
        aid = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
        orders.add(tuple(await _attempt_question_order(client, aid)))
    assert len(orders) > 1, "per-attempt shuffle must vary the order across attempts"


async def test_shuffle_option_order_stable_and_no_answer_key(client):
    await register_actor(client, "shuf2_teacher@ex.com", "teacher")
    exam_id, qids = await _make_shuffled_exam(client)
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "shuf2_student@ex.com", "student")
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    first = await _option_order(client, a1, qids[0])
    second = await _option_order(client, a1, qids[0])
    assert first == second  # stable per attempt

    # The answer key must never be revealed to the student.
    rows = (await client.get(f"/api/v1/attempts/{a1}/questions")).json()
    for r in rows:
        assert r["correct_answer"] is None
        for o in r["options"]:
            assert o.get("is_correct") in (None,)


async def test_score_identical_with_and_without_shuffle(client):
    """Shuffling must not change the score (labels stay canonical)."""
    await register_actor(client, "shuf3_teacher@ex.com", "teacher")
    exam_id, qids = await _make_shuffled_exam(client)
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "shuf3_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]

    # Answer every MC question correctly using canonical label "A" (the correct
    # option is always the first by canonical position).
    for qid in qids:
        r = await client.put(
            f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
        )
        assert r.status_code == 200, r.text
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200, submit.text
    # All correct regardless of the shuffled display order -> perfect score.
    assert submit.json()["score_bp"] == 10000
