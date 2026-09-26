"""Question bank listing and reuse across exams (C30)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _exam(teacher, title="Bank Exam") -> str:
    exam = await teacher.client.post(
        "/api/v1/exams", json={"title": title, "duration_minutes": 20}
    )
    return exam.json()["id"]


async def _add(teacher, exam_id, prompt="Soal bank nomor satu?") -> dict:
    r = await teacher.client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": prompt,
            "qtype": "multiple_choice",
            "options": [
                {"text": "Benar", "is_correct": True},
                {"text": "Salah", "is_correct": False},
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_bank_lists_and_attaches_question(make_actor):
    teacher = await make_actor("bank_t@ex.com", "teacher")
    exam_a = await _exam(teacher, "Ex A")
    q = await _add(teacher, exam_a, "Soal yang bisa dipakai ulang?")

    exam_b = await _exam(teacher, "Ex B")
    # Bank lists the question.
    bank = await teacher.client.get("/api/v1/questions/bank")
    assert bank.status_code == 200, bank.text
    assert any(row["id"] == q["id"] for row in bank.json())

    # Attach a copy into exam B.
    attach = await teacher.client.post(
        f"/api/v1/exams/{exam_b}/questions/attach", json={"question_id": q["id"]}
    )
    assert attach.status_code == 201, attach.text
    clone = attach.json()
    assert clone["id"] != q["id"]
    assert clone["exam_id"] == exam_b
    assert clone["prompt"] == q["prompt"]
    # Options were copied.
    assert len(clone["options"]) == 2

    # exam A still has its original question (list not moved).
    a_questions = await teacher.client.get(f"/api/v1/exams/{exam_a}")
    assert any(x["id"] == q["id"] for x in a_questions.json()["questions"])


async def test_deleting_exam_keeps_bank_question(make_actor):
    teacher = await make_actor("bank2_t@ex.com", "teacher")
    exam_a = await _exam(teacher, "Del")
    q = await _add(teacher, exam_a, "Soal tetap ada setelah ujian dihapus?")

    # Attach into exam B, then delete exam B.
    exam_b = await _exam(teacher, "Del2")
    await teacher.client.post(
        f"/api/v1/exams/{exam_b}/questions/attach", json={"question_id": q["id"]}
    )
    dele = await teacher.client.delete(f"/api/v1/exams/{exam_b}")
    assert dele.status_code == 204, dele.text

    # The source question still exists in the bank.
    bank = await teacher.client.get("/api/v1/questions/bank")
    assert any(row["id"] == q["id"] for row in bank.json())


async def test_cannot_attach_someone_elses_question(make_actor):
    owner = await make_actor("bank3_owner@ex.com", "teacher")
    exam_a = await _exam(owner, "Owner")
    q = await _add(owner, exam_a)

    other = await make_actor("bank3_other@ex.com", "teacher")
    exam_b = await _exam(other, "Other")
    r = await other.client.post(
        f"/api/v1/exams/{exam_b}/questions/attach", json={"question_id": q["id"]}
    )
    assert r.status_code == 403, r.text


async def test_bank_filters_by_qtype_and_query(make_actor):
    teacher = await make_actor("bank_filter_t@ex.com", "teacher")
    exam = await _exam(teacher, "Filter Exam")

    # Add a multiple_choice question
    await teacher.client.post(
        f"/api/v1/exams/{exam}/questions",
        json={
            "prompt": "Berapakah hasil dari 5 dikali 5?",
            "qtype": "multiple_choice",
            "options": [
                {"text": "25", "is_correct": True},
                {"text": "20", "is_correct": False},
            ],
        },
    )

    # Add an essay question
    await teacher.client.post(
        f"/api/v1/exams/{exam}/questions",
        json={
            "prompt": "Jelaskan siklus fotosintesis pada tumbuhan hijau secara detail.",
            "qtype": "essay",
            "correct_answer": "Fotosintesis membutuhkan cahaya matahari, CO2, dan air.",
        },
    )

    # Filter by qtype=essay
    res_essay = await teacher.client.get("/api/v1/questions/bank?qtype=essay")
    assert res_essay.status_code == 200
    essay_data = res_essay.json()
    assert len(essay_data) == 1
    assert "fotosintesis" in essay_data[0]["prompt"]
    assert essay_data[0]["qtype"] == "essay"

    # Filter by qtype=multiple_choice
    res_mc = await teacher.client.get("/api/v1/questions/bank?qtype=multiple_choice")
    assert res_mc.status_code == 200
    mc_data = res_mc.json()
    assert len(mc_data) == 1
    assert "5 dikali 5" in mc_data[0]["prompt"]
    assert mc_data[0]["qtype"] == "multiple_choice"

    # Search query
    res_search = await teacher.client.get("/api/v1/questions/bank?query=tumbuhan")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert len(search_data) == 1
    assert "fotosintesis" in search_data[0]["prompt"]

    # Search non-matching query
    res_empty = await teacher.client.get("/api/v1/questions/bank?query=tidak_ditemukan_xyz")
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0

