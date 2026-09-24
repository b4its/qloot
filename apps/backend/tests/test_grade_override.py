"""Teacher manual score override with audit + reward reversal (C23)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _mc_exam(teacher) -> tuple[str, str]:
    exam = await teacher.client.post(
        "/api/v1/exams",
        json={"title": "Override Exam", "duration_minutes": 30, "max_attempts": 5},
    )
    exam_id = exam.json()["id"]
    q = await teacher.client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Ibu kota Indonesia?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "Jakarta", "is_correct": True},
                {"text": "Bandung", "is_correct": False},
            ],
        },
    )
    qid = q.json()["id"]
    await teacher.client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, qid


async def test_override_changes_score_and_is_audited(make_actor, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import AuditLog

    teacher = await make_actor("ov_teacher@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)

    student = await make_actor("ov_student@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]
    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
    )
    submit = await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.json()["score_bp"] == 10000

    ov = await teacher.client.post(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}/override",
        json={"score_bp": 0, "feedback": "Jawaban kurang tepat"},
    )
    assert ov.status_code == 200, ov.text
    assert ov.json()["score_bp"] == 0

    result = await teacher.client.get(f"/api/v1/attempts/{attempt_id}/result")
    assert result.json()["attempt"]["score_bp"] == 0
    assert result.json()["attempt"]["passed"] is False

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        audits = (
            await s.execute(
                select(AuditLog).where(AuditLog.action == "exam.answer_override")
            )
        ).scalars().all()
    assert any(a.entity_id == attempt_id for a in audits)


async def test_override_reverses_perfect_exam_reward(make_actor, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.wallet import RewardAllocation

    teacher = await make_actor("ov2_teacher@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)

    student = await make_actor("ov2_student@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]
    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
    )
    await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        allocs = (
            await s.execute(
                select(RewardAllocation).where(RewardAllocation.reward_type == "perfect_exam")
            )
        ).scalars().all()
    assert any(a.status in ("pending", "confirmed") for a in allocs)

    # Downgrade the attempt so it is no longer perfect.
    await teacher.client.post(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}/override",
        json={"score_bp": 0, "feedback": None},
    )

    async with sm() as s:
        allocs2 = (
            await s.execute(
                select(RewardAllocation).where(RewardAllocation.reward_type == "perfect_exam")
            )
        ).scalars().all()
    assert any(a.status == "cancelled" for a in allocs2)


async def test_override_only_by_owner(make_actor):
    owner = await make_actor("ov3_owner@ex.com", "teacher")
    exam_id, qid = await _mc_exam(owner)
    student = await make_actor("ov3_student@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]
    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
    )
    await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")

    other = await make_actor("ov3_other@ex.com", "teacher")
    r = await other.client.post(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}/override",
        json={"score_bp": 100, "feedback": None},
    )
    assert r.status_code == 403, r.text
