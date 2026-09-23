"""Reward sources beyond quest/task: perfect exam, quiz master, course completion.

Closes WEB3-03 — these events used to pay zero OPT despite README claims.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _make_mc_exam(teacher):
    exam = await teacher.client.post(
        "/api/v1/exams",
        json={
            "title": "Reward Exam",
            "duration_minutes": 15,
            "passing_score_bp": 6000,
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    q = await teacher.client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "2 + 2 = ?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "4", "is_correct": True},
                {"text": "5", "is_correct": False},
            ],
        },
    )
    assert q.status_code == 201, q.text
    await teacher.client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, q.json()["id"]


async def _take_perfect(student, exam_id, qid):
    attempt_id = (await student.client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await student.client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"}
    )
    submit = await student.client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "graded"
    assert submit.json()["score_bp"] == 10000
    return attempt_id


async def _rewards(actor):
    r = await actor.client.get("/api/v1/wallet/rewards")
    assert r.status_code == 200, r.text
    return r.json()


async def test_perfect_exam_and_quiz_master_pay_opt(make_actor):
    teacher = await make_actor("rw_teacher@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(teacher)

    student = await make_actor("rw_student@ex.com", "student")
    attempt_id = await _take_perfect(student, exam_id, qid)

    rewards = await _rewards(student)
    kinds = sorted(
        x["reward_type"] for x in rewards if x.get("reward_type") in {"perfect_exam", "quiz_master"}
    )
    assert kinds == ["perfect_exam", "quiz_master"], rewards

    wallet = await student.client.get("/api/v1/wallet")
    assert wallet.json()["available"] >= 100 + 30

    # Re-trigger grading of the same attempt: must not double-pay.
    before = len(await _rewards(student))
    await student.client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    after = await _rewards(student)
    assert len(after) == before, "regrade must not create duplicate rewards"


async def test_course_completion_pays_opt(make_actor):
    teacher = await make_actor("cc_teacher@ex.com", "teacher")
    course = await teacher.client.post(
        "/api/v1/courses",
        json={"title": "Kursus Reward", "class_code": "1A", "class_type": "IPA"},
    )
    course_id = course.json()["id"]
    lesson = await teacher.client.post(
        f"/api/v1/courses/{course_id}/lessons", json={"title": "Pelajaran 1", "position": 0}
    )
    assert lesson.status_code == 201, lesson.text
    lesson_id = lesson.json()["id"]

    student = await make_actor("cc_student@ex.com", "student", class_code="1A", class_type="IPA")
    prog = await student.client.post(
        f"/api/v1/lessons/{lesson_id}/progress",
        json={"progress_percent": 100, "completed": True},
    )
    assert prog.status_code == 200, prog.text

    rewards = await _rewards(student)
    assert any(x.get("reward_type") == "course_completion" for x in rewards), rewards

    count = len([x for x in rewards if x.get("reward_type") == "course_completion"])
    await student.client.post("/api/v1/certificates/sync")
    rewards2 = await _rewards(student)
    count2 = len([x for x in rewards2 if x.get("reward_type") == "course_completion"])
    assert count2 == count == 1
