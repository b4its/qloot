"""True/false, multi-select and numeric question types (C28)."""

from __future__ import annotations

import pytest

from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def _exam(client) -> str:
    exam = await client.post(
        "/api/v1/exams",
        json={"title": "Types Exam", "duration_minutes": 30, "max_attempts": 5},
    )
    exam_id = exam.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id


async def _add(client, exam_id, payload) -> dict:
    r = await client.post(f"/api/v1/exams/{exam_id}/questions", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_true_false_graded_deterministically(client):
    await register_actor(client, "tf_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Bumi itu bulat.",
            "qtype": "true_false",
            "correct_answer": "true",
            "position": 0,
        },
    )
    assert q["qtype"] == "true_false"
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "tf_student@ex.com", "student")
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a1}/answers/{q['id']}", json={"answer_text": "true"})
    s1 = await client.post(f"/api/v1/attempts/{a1}/submit")
    assert s1.json()["score_bp"] == 10000

    a2 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a2}/answers/{q['id']}", json={"answer_text": "false"})
    s2 = await client.post(f"/api/v1/attempts/{a2}/submit")
    assert s2.json()["score_bp"] == 0


async def test_true_false_rejects_bad_key_and_answer(client):
    await register_actor(client, "tf2_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    bad = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Pernyataan?", "qtype": "true_false", "correct_answer": "maybe"},
    )
    assert bad.status_code == 422, bad.text


async def test_multi_select_partial_credit(client):
    await register_actor(client, "ms_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Pilih semua bilangan genap.",
            "qtype": "multi_select",
            "position": 0,
            "options": [
                {"text": "2", "is_correct": True},
                {"text": "4", "is_correct": True},
                {"text": "3", "is_correct": False},
                {"text": "5", "is_correct": False},
            ],
        },
    )
    assert q["answer_json"]["correct"] == ["A", "B"]
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "ms_student@ex.com", "student")
    # All correct -> 100%.
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(
        f"/api/v1/attempts/{a1}/answers/{q['id']}", json={"answer_text": '["A","B"]'}
    )
    s1 = await client.post(f"/api/v1/attempts/{a1}/submit")
    assert s1.json()["score_bp"] == 10000

    # Half correct, no wrong -> 50%.
    a2 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a2}/answers/{q['id']}", json={"answer_text": '["A"]'})
    s2 = await client.post(f"/api/v1/attempts/{a2}/submit")
    assert s2.json()["score_bp"] == 5000

    # One right + one wrong -> (1-1)/2 = 0%.
    a3 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(
        f"/api/v1/attempts/{a3}/answers/{q['id']}", json={"answer_text": '["A","C"]'}
    )
    s3 = await client.post(f"/api/v1/attempts/{a3}/submit")
    assert s3.json()["score_bp"] == 0

    # Selecting everything does not beat selecting exactly the right ones.
    a4 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(
        f"/api/v1/attempts/{a4}/answers/{q['id']}",
        json={"answer_text": '["A","B","C","D"]'},
    )
    s4 = await client.post(f"/api/v1/attempts/{a4}/submit")
    assert s4.json()["score_bp"] == 0


async def test_numeric_tolerance(client):
    await register_actor(client, "num_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    q = await _add(
        client,
        exam_id,
        {
            "prompt": "Berapa 2 + 2?",
            "qtype": "numeric",
            "position": 0,
            "answer_json": {"value": 4, "tolerance": 0.5},
        },
    )
    await client.post("/api/v1/auth/logout")
    await register_actor(client, "num_student@ex.com", "student")

    # Within tolerance -> full credit.
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a1}/answers/{q['id']}", json={"answer_text": "4.4"})
    s1 = await client.post(f"/api/v1/attempts/{a1}/submit")
    assert s1.json()["score_bp"] == 10000

    # Outside tolerance -> zero.
    a2 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a2}/answers/{q['id']}", json={"answer_text": "5"})
    s2 = await client.post(f"/api/v1/attempts/{a2}/submit")
    assert s2.json()["score_bp"] == 0


async def test_numeric_requires_value(client):
    await register_actor(client, "num2_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    bad = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Nilai x?", "qtype": "numeric"},
    )
    assert bad.status_code == 422, bad.text


async def test_unsupported_qtype_rejected(client):
    await register_actor(client, "uq_teacher@ex.com", "teacher")
    exam_id = await _exam(client)
    bad = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Soal aneh?", "qtype": "telepathy"},
    )
    assert bad.status_code == 422, bad.text
