"""Multiple-choice questions: authoring (teacher CRUD) + taking + instant grading."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="MC User")


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


async def test_mc_only_submit_creates_no_grading_job(client, engine):
    """An MC-only exam is graded instantly and never enqueues an AI job."""
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import GradingJob

    await _register(client, "mc_job_teacher@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "mc_job_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.json()["status"] == "graded"

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        n = (
            await s.execute(
                select(func.count())
                .select_from(GradingJob)
                .where(GradingJob.attempt_id == __import__("uuid").UUID(attempt_id))
            )
        ).scalar_one()
    assert n == 0


async def test_mixed_exam_enqueues_job_and_grades_correctly(client, engine):
    """An MC + essay exam grades MC instantly, enqueues a job for the essay, and
    the essay portion is graded by the worker."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.exam import GradingJob
    from app.services.grading_service import process_grading_job

    await _register(client, "mixed_teacher@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Campuran", "passing_score_bp": 5000})
    exam_id = exam.json()["id"]
    mc = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "2 + 2 = ?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [{"text": "4", "is_correct": True}, {"text": "5", "is_correct": False}],
        },
    )
    mc_id = mc.json()["id"]
    es = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Jelaskan fotosintesis",
            "correct_answer": "Proses tumbuhan",
            "position": 1,
        },
    )
    essay_id = es.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "mixed_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{mc_id}", json={"answer_text": "A"})
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{essay_id}",
        json={"answer_text": "Fotosintesis adalah proses tumbuhan."},
    )
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    # Mixed exam waits for the worker.
    assert submit.json()["status"] == "submitted"

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        import uuid as _uuid

        job = (
            await s.execute(
                select(GradingJob).where(GradingJob.attempt_id == _uuid.UUID(attempt_id))
            )
        ).scalars().first()
        assert job is not None
        await process_grading_job(s, job.id)
        await s.commit()

    result = await client.get(f"/api/v1/attempts/{attempt_id}/result")
    body = result.json()
    assert body["attempt"]["status"] == "graded"
    # MC answer scored (0 or full) and the essay was graded too.
    scores = {a["question_id"]: a["score_bp"] for a in body["answers"]}
    assert scores[mc_id] == 10000  # correct MC
    assert scores[essay_id] is not None  # essay graded


async def test_result_returns_exam_even_when_not_graded(client):
    """The result endpoint always returns exam context (result page can render
    before the worker finishes / after the exam is closed)."""
    await _register(client, "res_teacher@ex.com", "teacher")
    exam = await client.post("/api/v1/exams", json={"title": "Hasil Konteks"})
    exam_id = exam.json()["id"]
    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": "Tulis esai", "correct_answer": "acuan", "position": 0},
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "res_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    result = await client.get(f"/api/v1/attempts/{attempt_id}/result")
    body = result.json()
    # Exam context present even though the attempt is still in progress.
    assert body["exam"]["id"] == exam_id
    assert body["exam"]["title"] == "Hasil Konteks"
    # No answer key revealed before grading.
    assert body["questions"] == []


async def test_exam_results_review_shows_students_questions_and_correctness(client):
    """The per-exam review lists each student, their questions, answers and
    whether each multiple-choice answer was correct."""
    await _register(client, "rev_teacher@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)  # answer A = Jakarta (correct)
    await client.post("/api/v1/auth/logout")

    # Student 1 answers correctly, student 2 wrongly.
    await _register(client, "rev_stu_ok@ex.com", "student")
    a1 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a1}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{a1}/submit")
    await client.post("/api/v1/auth/logout")

    await _register(client, "rev_stu_bad@ex.com", "student")
    a2 = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{a2}/answers/{qid}", json={"answer_text": "B"})
    await client.post(f"/api/v1/attempts/{a2}/submit")
    await client.post("/api/v1/auth/logout")

    # Teacher reviews the whole exam.
    await client.post(
        "/api/v1/auth/login",
        json={"email": "rev_teacher@ex.com", "password": "Password123!"},
    )
    review = await client.get(f"/api/v1/exams/{exam_id}/results/review")
    assert review.status_code == 200, review.text
    body = review.json()
    assert body["exam"]["id"] == exam_id
    rows = {r["display_name"]: r for r in body["results"]}
    assert "MC User" in rows  # the shared full_name used by _register
    assert len(body["results"]) == 2

    ok = next(r for r in body["results"] if r["answers"][0]["is_correct"] is True)
    bad = next(r for r in body["results"] if r["answers"][0]["is_correct"] is False)
    assert ok["passed"] is True
    assert bad["passed"] is False

    q_ok = ok["answers"][0]
    assert q_ok["question_id"] == qid
    assert q_ok["qtype"] == "multiple_choice"
    assert q_ok["answer_text"] == "A"
    assert q_ok["answer_display"] == "Jakarta"
    assert q_ok["correct_answer"] == "A"
    assert q_ok["correct_display"] == "Jakarta"
    assert q_ok["score_bp"] == q_ok["max_score_bp"]

    q_bad = bad["answers"][0]
    assert q_bad["answer_text"] == "B"
    assert q_bad["answer_display"] == "Bandung"
    assert q_bad["is_correct"] is False
    assert q_bad["score_bp"] == 0


async def test_exam_results_review_is_owner_only(client):
    """A different teacher cannot read another teacher's exam review."""
    await _register(client, "rev_owner@ex.com", "teacher")
    exam_id, _qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "rev_other@ex.com", "teacher")
    denied = await client.get(f"/api/v1/exams/{exam_id}/results/review")
    assert denied.status_code == 403, denied.text
    await client.post("/api/v1/auth/logout")

    # A student is also rejected.
    await _register(client, "rev_stu@ex.com", "student")
    denied2 = await client.get(f"/api/v1/exams/{exam_id}/results/review")
    assert denied2.status_code == 403, denied2.text


async def test_teacher_submissions_exposes_student_and_correctness(client):
    """The flat submissions feed carries the student's name and, for MC, whether
    the answer was correct."""
    await _register(client, "sub_teacher@ex.com", "teacher")
    exam_id, qid = await _make_mc_exam(client)
    await client.post("/api/v1/auth/logout")

    await _register(client, "sub_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{qid}", json={"answer_text": "A"})
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login",
        json={"email": "sub_teacher@ex.com", "password": "Password123!"},
    )
    subs = await client.get("/api/v1/teacher/submissions")
    assert subs.status_code == 200, subs.text
    row = next(r for r in subs.json() if r["question_id"] == qid)
    assert row["student_name"] == "MC User"
    assert row["qtype"] == "multiple_choice"
    assert row["answer_display"] == "Jakarta"
    assert row["correct_display"] == "Jakarta"
    assert row["is_correct"] is True


async def _add_essay_question(client, exam_id, prompt="Jelaskan fotosintesis.", position=0):
    q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={"prompt": prompt, "qtype": "essay", "position": position},
    )
    assert q.status_code == 201, q.text
    return q.json()["id"]


async def test_exam_list_and_detail_expose_question_composition(client):
    """The exam list/detail classify an exam as MC, essay or mixed via counts."""
    await _register(client, "comp_teacher@ex.com", "teacher")

    # Pure multiple-choice exam.
    mc_id, _ = await _make_mc_exam(client)
    # Pure essay exam.
    essay_exam = await client.post("/api/v1/exams", json={"title": "Ujian Esai Murni"})
    essay_id = essay_exam.json()["id"]
    await _add_essay_question(client, essay_id)
    await _add_essay_question(client, essay_id, prompt="Apa itu gravitasi?", position=1)
    # Mixed exam: one MC + one essay.
    mixed_exam = await client.post("/api/v1/exams", json={"title": "Ujian Campuran"})
    mixed_id = mixed_exam.json()["id"]
    await client.post(
        f"/api/v1/exams/{mixed_id}/questions",
        json={
            "prompt": "Hasil dari 3 x 3?",
            "qtype": "multiple_choice",
            "position": 0,
            "options": [
                {"text": "9", "is_correct": True},
                {"text": "6", "is_correct": False},
            ],
        },
    )
    await _add_essay_question(client, mixed_id, prompt="Uraikan hukum Newton.", position=1)

    listing = await client.get("/api/v1/exams?limit=50")
    assert listing.status_code == 200, listing.text
    by_id = {e["id"]: e for e in listing.json()}

    assert by_id[mc_id]["question_count"] == 1
    assert by_id[mc_id]["mc_count"] == 1
    assert by_id[mc_id]["essay_count"] == 0

    assert by_id[essay_id]["question_count"] == 2
    assert by_id[essay_id]["mc_count"] == 0
    assert by_id[essay_id]["essay_count"] == 2

    assert by_id[mixed_id]["question_count"] == 2
    assert by_id[mixed_id]["mc_count"] == 1
    assert by_id[mixed_id]["essay_count"] == 1

    # The single-exam detail endpoint carries the same composition.
    detail = await client.get(f"/api/v1/exams/{mixed_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["question_count"] == 2
    assert detail.json()["mc_count"] == 1
    assert detail.json()["essay_count"] == 1


async def test_question_weight_shifts_total_score(client):
    """C27: a question with double weight moves the score proportionally."""
    await _register(client, "weight_teacher@ex.com", "teacher")
    exam = await client.post(
        "/api/v1/exams",
        json={"title": "Weighted", "duration_minutes": 20, "max_attempts": 5},
    )
    exam_id = exam.json()["id"]
    # Q1 weight 10000 (100%), Q2 weight 5000 (50%) -> answering only Q1 gives
    # 10000 / (10000 + 5000) = 66.67%.
    q1 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Soal berbobot besar?",
            "qtype": "multiple_choice",
            "max_score_bp": 10000,
            "position": 0,
            "options": [
                {"text": "Benar", "is_correct": True},
                {"text": "Salah", "is_correct": False},
            ],
        },
    )
    q1_id = q1.json()["id"]
    q2 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        json={
            "prompt": "Soal berbobot kecil?",
            "qtype": "multiple_choice",
            "max_score_bp": 5000,
            "position": 1,
            "options": [
                {"text": "Benar", "is_correct": True},
                {"text": "Salah", "is_correct": False},
            ],
        },
    )
    q2_id = q2.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    await client.post("/api/v1/auth/logout")

    await _register(client, "weight_student@ex.com", "student")
    attempt_id = (await client.post(f"/api/v1/exams/{exam_id}/attempts")).json()["id"]
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q1_id}", json={"answer_text": "A"})
    # Deliberately wrong on the low-weight question.
    await client.put(f"/api/v1/attempts/{attempt_id}/answers/{q2_id}", json={"answer_text": "B"})
    submit = await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    assert submit.status_code == 200, submit.text
    # 10000 * 10000 / 15000 = 6667.
    assert submit.json()["score_bp"] == 6667
