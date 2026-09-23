"""Exam retake policy: max_attempts enforcement (C20)."""

from __future__ import annotations

import pytest

from tests.helpers import register_actor

pytestmark = pytest.mark.integration


async def _make_exam(client, *, max_attempts: int) -> str:
    exam = await client.post(
        "/api/v1/exams",
        json={
            "title": "Retake Exam",
            "duration_minutes": 30,
            "passing_score_bp": 5000,
            "max_attempts": max_attempts,
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id


async def test_attempts_beyond_limit_are_rejected(client):
    await register_actor(client, "retake_teacher@ex.com", "teacher")
    exam_id = await _make_exam(client, max_attempts=2)
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "retake_student@ex.com", "student")
    assert (await client.post(f"/api/v1/exams/{exam_id}/attempts")).status_code == 201
    assert (await client.post(f"/api/v1/exams/{exam_id}/attempts")).status_code == 201
    # Third attempt is beyond the limit.
    third = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    assert third.status_code == 409, third.text
    assert "percobaan" in third.json()["error"]["message"].lower()


async def test_zero_max_attempts_is_unlimited(client):
    await register_actor(client, "unl_teacher@ex.com", "teacher")
    exam_id = await _make_exam(client, max_attempts=0)
    await client.post("/api/v1/auth/logout")

    await register_actor(client, "unl_student@ex.com", "student")
    for _ in range(4):
        assert (await client.post(f"/api/v1/exams/{exam_id}/attempts")).status_code == 201


async def test_max_attempts_visible_in_exam_out(client):
    await register_actor(client, "vis_teacher@ex.com", "teacher")
    exam_id = await _make_exam(client, max_attempts=3)
    exam = await client.get(f"/api/v1/exams/{exam_id}")
    assert exam.status_code == 200, exam.text
    assert exam.json()["max_attempts"] == 3
