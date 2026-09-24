"""Exam analytics: distribution, difficulty, discrimination and CSV (C31)."""

from __future__ import annotations

import csv
import io

import pytest

pytestmark = pytest.mark.integration


async def _mc_exam(teacher) -> tuple[str, str]:
    exam = await teacher.client.post(
        "/api/v1/exams",
        json={"title": "Analytics Exam", "duration_minutes": 30, "max_attempts": 20},
    )
    exam_id = exam.json()["id"]
    # One MC question (deterministic).
    q = await teacher.client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Ibu kota Indonesia adalah?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "Jakarta", "is_correct": True},
                {"text": "Bandung", "is_correct": False},
            ],
        },
    )
    await teacher.client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, q.json()["id"]


async def _attempt(student, exam_id, qid, correct: bool) -> int:
    a = (await student.client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await student.client.put(
        f"/api/v1/attempts/{a}/answers/{qid}", json={"answer_text": "A" if correct else "B"}
    )
    s = await student.client.post(f"/api/v1/attempts/{a}/submit")
    return s.json()["score_bp"]


async def test_analytics_distribution_and_difficulty(make_actor):
    teacher = await make_actor("an_t@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)

    # Three students: 2 correct, 1 wrong -> difficulty p = 2/3.
    for i, correct in enumerate([True, True, False]):
        s = await make_actor(f"an_s{i}@ex.com", "student")
        await _attempt(s, exam_id, qid, correct)

    report = await teacher.client.get(f"/api/v1/exams/{exam_id}/analytics")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["attempts"] == 3
    # Two perfect (bucket 9) and one zero (bucket 0).
    assert body["histogram"][9] == 2
    assert body["histogram"][0] == 1

    q = body["questions"][0]
    assert q["answered"] == 3
    # difficulty = mean ratio = (1 + 1 + 0)/3 = 0.6667 -> 6667 bp.
    assert q["difficulty_bp"] == 6667
    # Discrimination is deterministic; > 0 here (correct answers score higher).
    assert q["discrimination"] > 0


async def test_analytics_csv_parses(make_actor):
    teacher = await make_actor("an2_t@ex.com", "teacher")
    exam_id, qid = await _mc_exam(teacher)
    s = await make_actor("an2_s@ex.com", "student")
    await _attempt(s, exam_id, qid, True)

    r = await teacher.client.get(f"/api/v1/exams/{exam_id}/analytics.csv")
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][0] == "question_id"
    assert len(rows) == 2  # header + one question
    assert rows[1][1] == "multiple_choice"


async def test_analytics_not_shown_to_non_owner(make_actor):
    owner = await make_actor("an3_owner@ex.com", "teacher")
    exam_id, _qid = await _mc_exam(owner)
    other = await make_actor("an3_other@ex.com", "teacher")
    r = await other.client.get(f"/api/v1/exams/{exam_id}/analytics")
    assert r.status_code == 403, r.text
