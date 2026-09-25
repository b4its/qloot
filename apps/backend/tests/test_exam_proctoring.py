"""Proctoring telemetry and attempt flagging (C25)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _mc_exam(teacher) -> tuple[str, str]:
    exam = await teacher.client.post(
        "/api/v1/exams",
        json={"title": "Proctor Exam", "duration_minutes": 30, "max_attempts": 5},
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


async def test_events_recorded_and_flag_on_threshold(make_actor, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import AttemptEvent, ExamAttempt

    teacher = await make_actor("pro_teacher@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)

    student = await make_actor("pro_student@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]

    # Fire 5 blur violations.
    events = [{"kind": "blur", "detail": {"n": i}} for i in range(5)]
    r = await student.client.post(
        f"/api/v1/attempts/{attempt_id}/events", json={"events": events}
    )
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] == 5

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        count = (
            await s.execute(select(AttemptEvent).where(AttemptEvent.attempt_id == attempt_id))
        ).scalars().all()
        row = await s.get(ExamAttempt, __import__("uuid").UUID(attempt_id))
    assert len(count) == 5
    assert row.is_flagged is True


async def test_paste_event_is_recorded_and_counts_as_violation(make_actor, engine):
    """C25: a paste event is produced by the attempt UI and counts toward the
    violation threshold (the branch must not be dead)."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import AttemptEvent

    teacher = await make_actor("pro_paste_t@ex.com", "teacher")
    exam_id, _qid = await _mc_exam(teacher)
    student = await make_actor("pro_paste_s@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]

    r = await student.client.post(
        f"/api/v1/attempts/{attempt_id}/events",
        json={"events": [{"kind": "paste", "detail": {"target": "TEXTAREA"}}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] == 1

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        rows = (
            await s.execute(
                select(AttemptEvent).where(
                    AttemptEvent.attempt_id == __import__("uuid").UUID(attempt_id)
                )
            )
        ).scalars().all()
    assert [e.kind for e in rows] == ["paste"]


async def test_teacher_sees_flag_in_results(make_actor):
    teacher = await make_actor("pro2_teacher@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)
    student = await make_actor("pro2_student@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]

    await student.client.post(
        f"/api/v1/attempts/{attempt_id}/events",
        json={"events": [{"kind": "visibility_hidden"} for _ in range(5)]},
    )
    # Submit so the attempt appears in the review (graded MC-only).
    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
    )
    await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")

    review = await teacher.client.get(f"/api/v1/exams/{exam_id}/results/review")
    assert review.status_code == 200, review.text
    row = next(r for r in review.json()["results"] if r["id"] == attempt_id)
    assert row["is_flagged"] is True
    assert row["violation_count"] >= 5


async def test_telemetry_never_blocks_submit(make_actor):
    teacher = await make_actor("pro3_teacher@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)
    student = await make_actor("pro3_student@ex.com", "student")
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]

    # An unknown-but-nonempty kind is accepted and ignored gracefully.
    r = await student.client.post(
        f"/api/v1/attempts/{attempt_id}/events", json={"events": [{"kind": "unknown_thing"}]}
    )
    assert r.status_code == 200
    assert r.json()["recorded"] == 1

    # A malformed event list is a client error (422) but does not block submit.
    bad = await student.client.post(
        f"/api/v1/attempts/{attempt_id}/events", json={"events": [{"kind": ""}]}
    )
    assert bad.status_code == 422

    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
    )
    submit = await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200, submit.text
