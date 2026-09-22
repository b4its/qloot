"""Multiple-choice questions: authoring (teacher CRUD) + taking + instant grading."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "MC User", "password": "Password123!", "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _make_mc_exam(client, passing_bp=6000):
    """Create + publish an MC-only exam; return (exam_id, question_id, labels)."""
    exam = await client.post(
        "/api/v1/exams",
        json={
            "title": "Kuis Pilihan Ganda",
            "duration_minutes": 15,
            "passing_score_bp": passing_bp,
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Ibu kota Indonesia adalah?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "Jakarta", "is_correct": True},
                {"text": "Bandung", "is_correct": False},
                {"text": "Surabaya", "is_correct": False},
                {"text": "Medan", "is_correct": False},
            ],
        },
    )
    assert q.status_code == 201, q.text
    pub = await client.post(f"/api/v1/exams/{exam_id}/publish")
    assert pub.status_code == 200
    return exam_id, q.json()["id"]


async def test_teacher_creates_mc_question_with_options(client):
    await _register(client, "mc_teacher@ex.com", "teacher")
    created = await client.post(
        "/api/v1/exams",
        json={"title": "MC Exam"},
    )
    exam_id = created.json()["id"]
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Berapa 2 + 2?",
            "qtype": "multiple_choice",
            "options": [
                {"text": "3", "is_correct": False},
                {"text": "4", "is_correct": True},
            ],
        },
    )
    assert q.status_code == 201, q.text
    body = q.json()
    assert body["qtype"] == "multiple_choice"
    labels = [o["label"] for o in body["options"]]
    assert labels == ["A", "B"]
    # The owner sees the answer key.
    assert [o for o in body["options"] if o["is_correct"]][0]["text"] == "4"
    assert body["correct_answer"] == "B"


async def test_mc_requires_exactly_one_correct_and_min_options(client):
    await _register(client, "mc_validate@ex.com", "teacher")
    exam_id = (await client.post("/api/v1/exams", json={"title": "Valid"})).json()["id"]

    # No correct option.
    bad1 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Pilih satu",
            "qtype": "multiple_choice",
            "options": [{"text": "a"}, {"text": "b"}],
        },
    )
    assert bad1.status_code == 422, bad1.text

    # Two correct options.
    bad2 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Pilih satu",
            "qtype": "multiple_choice",
            "options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}],
        },
    )
    assert bad2.status_code == 422, bad2.text

    # Too few options.
    bad3 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Pilih satu",
            "qtype": "multiple_choice",
            "options": [{"text": "a", "is_correct": True}],
        },
    )
    assert bad3.status_code == 422, bad3.text


async def test_teacher_edits_and_deletes_mc_options(client):
    await _register(client, "mc_edit@ex.com", "teacher")
    exam_id = (await client.post("/api/v1/exams", json={"title": "Edit"})).json()["id"]
    q = (
        await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={
                "prompt": "Soal awal",
                "qtype": "multiple_choice",
                "options": [
                    {"text": "benar", "is_correct": True},
                    {"text": "salah", "is_correct": False},
                ],
            },
        )
    ).json()
    qid = q["id"]

    # Replace options (change the correct one + add a third).
    upd = await client.patch(
        f"/api/v1/questions/{qid}",
        json={
            "options": [
                {"text": "salah", "is_correct": False},
                {"text": "benar", "is_correct": True},
                {"text": "lain", "is_correct": False},
            ]
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert len(body["options"]) == 3
    assert body["correct_answer"] == "B"

    # Delete the question.
    dele = await client.delete(f"/api/v1/questions/{qid}")
    assert dele.status_code == 204, dele.text


async def test_student_detail_hides_correct_option(client):
    await _register(client, "mc_teacher2@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "mc_student1@ex.com", "student")
    detail = await client.get(f"/api/v1/exams/{exam_id}")
    assert detail.status_code == 200, detail.text
    q = detail.json()["questions"][0]
    assert q["qtype"] == "multiple_choice"
    assert q["correct_answer"] is None
    # Choices are present but none is flagged correct.
    assert len(q["options"]) == 4
    assert all(o["is_correct"] is None for o in q["options"])


async def test_student_answers_mc_and_is_graded_instantly(client):
    await _register(client, "mc_teacher3@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "mc_student2@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]

    # An invalid choice label is rejected.
    bad = await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "Z"}
    )
    assert bad.status_code == 422, bad.text

    # Correct choice (A = Jakarta).
    ok = await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    assert ok.status_code == 200, ok.text

    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200, submit.text
    # MC-only exam is graded instantly at submit (no AI worker needed).
    assert submit.json()["status"] == "graded"
    assert submit.json()["score_bp"] == 10000

    result = await client.get(f"/api/v1/attempts/{attempt_id}/result")
    body = result.json()
    assert body["attempt"]["passed"] is True
    assert len(body["answers"]) == 1
    assert body["answers"][0]["score_bp"] == 10000
    # Graded review reveals the correct option.
    assert any(o["is_correct"] for o in body["questions"][0]["options"])


async def test_student_wrong_mc_answer_scores_zero(client):
    await _register(client, "mc_teacher4@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "mc_student3@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "C"})
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200
    assert submit.json()["score_bp"] == 0
    assert submit.json()["passed"] is False


async def test_mc_ace_awards_quiz_master_badge(client):
    await _register(client, "mc_teacher5@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "mc_student4@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")

    badges = await client.get("/api/v1/me/badges")
    assert badges.status_code == 200, badges.text
    codes = {b["badge"]["code"] for b in badges.json()}
    assert "quiz_master" in codes


async def test_seed_mc_quiz_creates_valid_questions(session):
    """The demo seeder produces a valid, published multiple-choice quiz."""
    from sqlalchemy import select

    from app.db.seed_bulk import _seed_mc_quiz
    from app.models.exam import Exam, Question, QuestionOption
    from app.models.identity import User

    owner = User(
        id=__import__("uuid").uuid4(),
        email="seed_owner@ex.com",
        full_name="Seed Owner",
        password_hash="x",
        chain_user_ref="0x" + "ab" * 32,
    )
    session.add(owner)
    await session.flush()

    await _seed_mc_quiz(session, [owner])
    await session.flush()

    exam = (
        (
            await session.execute(
                select(Exam).where(Exam.title == "Kuis Pilihan Ganda — Pengetahuan Umum")
            )
        )
        .scalars()
        .first()
    )
    assert exam is not None and exam.is_active is True

    questions = (
        (await session.execute(select(Question).where(Question.exam_id == exam.id))).scalars().all()
    )
    assert len(questions) >= 3
    for q in questions:
        assert q.qtype == "multiple_choice"
        options = (
            (
                await session.execute(
                    select(QuestionOption).where(QuestionOption.question_id == q.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(options) >= 2
        assert len([o for o in options if o.is_correct]) == 1
        # correct_answer stays in sync with the correct option's label.
        assert q.correct_answer in {o.label for o in options if o.is_correct}
