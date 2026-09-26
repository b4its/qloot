"""Tests for exam question reordering."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Exam Teacher")


async def test_reorder_questions_success(client):
    # Teacher sets up an exam with 3 questions.
    await _register(client, "teacher_reorder@ex.com", "teacher")
    exam = await client.post(
        "/api/v1/exams",
        json={"title": "Ujian Reorder", "duration_minutes": 30, "passing_score_bp": 5000},
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]

    q1 = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": "Soal Pertama", "correct_answer": "A", "position": 0},
        )
    ).json()["id"]
    q2 = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": "Soal Kedua", "correct_answer": "B", "position": 1},
        )
    ).json()["id"]
    q3 = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": "Soal Ketiga", "correct_answer": "C", "position": 2},
        )
    ).json()["id"]

    # Reverse order: q3, q2, q1
    res = await client.post(
        f"/api/v1/exams/{exam_id}/questions/reorder",
        json={"question_ids": [q3, q2, q1]},
    )
    assert res.status_code == 200, res.text
    ordered = res.json()
    assert [q["id"] for q in ordered] == [q3, q2, q1]
    assert [q["position"] for q in ordered] == [0, 1, 2]

    # Verify persistent order via exam detail
    detail = (await client.get(f"/api/v1/exams/{exam_id}")).json()
    assert [q["id"] for q in detail["questions"]] == [q3, q2, q1]


async def test_reorder_questions_validation(client):
    await _register(client, "teacher_reorder_val@ex.com", "teacher")
    exam = (
        await client.post(
            "/api/v1/exams",
            json={"title": "Ujian Val", "duration_minutes": 30, "passing_score_bp": 5000},
        )
    ).json()
    exam_id = exam["id"]

    q1 = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": "Soal 1", "correct_answer": "A", "position": 0},
        )
    ).json()["id"]
    q2 = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": "Soal 2", "correct_answer": "B", "position": 1},
        )
    ).json()["id"]

    # Incomplete list (only q1, missing q2)
    res = await client.post(
        f"/api/v1/exams/{exam_id}/questions/reorder",
        json={"question_ids": [q1]},
    )
    assert res.status_code == 422

    # Foreign id included with q1 and q2
    foreign_id = "00000000-0000-0000-0000-000000000001"
    res2 = await client.post(
        f"/api/v1/exams/{exam_id}/questions/reorder",
        json={"question_ids": [q1, q2, foreign_id]},
    )
    assert res2.status_code == 422
