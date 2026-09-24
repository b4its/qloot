"""Cross-student plagiarism pass on essay answers (C26)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _essay_exam(teacher) -> tuple[str, str]:
    exam = await teacher.client.post(
        "/api/v1/exams",
        json={"title": "Plagiarism Exam", "duration_minutes": 30, "max_attempts": 5},
    )
    exam_id = exam.json()["id"]
    q = await teacher.client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Jelaskan proses fotosintesis pada tumbuhan hijau secara lengkap.",
            "correct_answer": "Fotosintesis mengubah cahaya menjadi energi",
            "position": 0,
        },
    )
    qid = q.json()["id"]
    await teacher.client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, qid


async def _submit_essay(student, exam_id, qid, text):
    attempt_id = (
        await student.client.post(f"/api/v1/exams/{exam_id}/attempts")
    ).json()["id"]
    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": text}
    )
    await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")
    return attempt_id


async def test_near_identical_essays_are_flagged(make_actor, engine):
    # Grade the essays directly so `graded_at` is set (the plagiarism pass only
    # considers graded answers); mock provider makes grading synchronous.
    teacher = await make_actor("plag_teacher@ex.com", "teacher")
    exam_id, qid = await _essay_exam(teacher)

    a = await make_actor("plag_a@ex.com", "student")
    b = await make_actor("plag_b@ex.com", "student")
    text = (
        "Fotosintesis adalah proses tumbuhan hijau mengubah cahaya matahari "
        "menjadi energi kimia dengan bantuan klorofil dan air serta karbon dioksida."
    )
    await _submit_essay(a, exam_id, qid, text)
    await _submit_essay(b, exam_id, qid, text)

    # Grade the two attempts (worker path) so their answers are marked graded.
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import ExamAttempt
    from app.services.grading_service import GradingService

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        attempts = (
            await s.execute(
                select(ExamAttempt).where(ExamAttempt.exam_id == __import__("uuid").UUID(exam_id))
            )
        ).scalars().all()
        for att in attempts:
            await GradingService(s).grade_attempt(att)
        await s.commit()

    report = await teacher.client.get(f"/api/v1/exams/{exam_id}/plagiarism")
    assert report.status_code == 200, report.text
    findings = report.json()["findings"]
    assert findings, "identical essays must be reported"
    assert findings[0]["similarity_bp"] >= 7000


async def test_distinct_essays_not_flagged(make_actor, engine):
    teacher = await make_actor("plag2_teacher@ex.com", "teacher")
    exam_id, qid = await _essay_exam(teacher)
    a = await make_actor("plag2_a@ex.com", "student")
    b = await make_actor("plag2_b@ex.com", "student")
    await _submit_essay(
        a, exam_id, qid, "Fotosintesis memakai cahaya matahari dan klorofil."
    )
    await _submit_essay(
        b, exam_id, qid, "Respirasi sel menguraikan glukosa menjadi karbon dioksida dan uap air."
    )

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import ExamAttempt
    from app.services.grading_service import GradingService

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        attempts = (
            await s.execute(
                select(ExamAttempt).where(ExamAttempt.exam_id == __import__("uuid").UUID(exam_id))
            )
        ).scalars().all()
        for att in attempts:
            await GradingService(s).grade_attempt(att)
        await s.commit()

    report = await teacher.client.get(f"/api/v1/exams/{exam_id}/plagiarism?threshold_bp=7000")
    assert report.status_code == 200, report.text
    assert report.json()["findings"] == []
