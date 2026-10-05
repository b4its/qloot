"""Regression tests for the realistic learning-timeline seeder.

These lock in the properties the demo data must have so dashboards, streaks and
analytics look real:

  * a believable *content* catalogue (real subjects, lessons, exams) instead of
    "…#001" filler;
  * **100–200 learning-activity records per month**, starting January 2025;
  * a coherent flow (every attempt belongs to a learner and is graded; lesson
    progress / certificates follow the lessons);
  * determinism + idempotency (re-running inserts nothing new and never raises).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.db import content, seed_timeline
from app.db.seed_bulk import det_uuid

pytestmark = pytest.mark.integration


async def _teacher(session, email: str = "tl_teacher@ex.com"):
    from app.core.security import hash_password
    from app.models.identity import Role, User, UserRole

    role_row = (await session.execute(select(Role).where(Role.name == "teacher"))).scalar_one()
    u = User(
        email=email,
        full_name="Guru Timeline",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + email.encode().hex()[:64].ljust(64, "0"),
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role_row.id))
    await session.flush()
    return u


async def _student(session, email: str, class_code: str, class_type: str):
    from app.core.security import hash_password
    from app.models.identity import Role, User, UserRole

    role_row = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    u = User(
        email=email,
        full_name=f"Siswa {class_code}",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + email.encode().hex()[:64].ljust(64, "0"),
        class_code=class_code,
        class_type=class_type,
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role_row.id))
    await session.flush()
    return u


async def _roster(session, n: int = 6):
    """Create n students spread across the real classes.

    Emails follow the seeder's ``student%@qloot.example`` convention so the
    timeline's roster loader picks them up.
    """
    students = []
    for i in range(n):
        cc, ct = content.CLASSES[i % len(content.CLASSES)]
        students.append(
            await _student(session, f"student_tl_{i}@qloot.example", cc, ct)
        )
    return students


# ---------------------------------------------------------------------------
# Pure helpers (no DB) — monthly calendar + volume
# ---------------------------------------------------------------------------
def test_month_starts_begins_january_2025():
    now = datetime(2025, 4, 15, tzinfo=UTC)
    months = seed_timeline.month_starts(now)
    assert months[0] == (2025, 1)
    assert months[-1] == (2025, 4)
    assert len(months) == 4


def test_monthly_volume_within_budget_and_deterministic():
    months = seed_timeline.month_starts(datetime(2026, 6, 1, tzinfo=UTC))
    assert months[0] == (2025, 1)
    for year, month in months:
        vol = seed_timeline.monthly_volume(year, month)
        assert 100 <= vol <= 200, f"{year}-{month} volume {vol} out of range"
        # Deterministic: same month always the same volume.
        assert seed_timeline.monthly_volume(year, month) == vol


def test_monthly_volume_varies_between_months():
    vols = {seed_timeline.monthly_volume(2025, m) for m in range(1, 13)}
    assert len(vols) > 1, "all months identical — not realistic"


def test_content_catalogue_is_realistic():
    # Real subjects, not placeholders.
    subs = content.subjects()
    assert "Matematika" in subs and "Fisika" in subs and "Sejarah" in subs
    assert all("#" not in s for s in subs)
    # Every subject has lessons and a multiple-choice exam with real questions.
    for subject in subs:
        lessons = content.lessons_for(subject)
        assert lessons, f"{subject} has no lessons"
        exam = content.exam_for(subject)
        assert exam is not None, f"{subject} has no exam"
        assert exam.questions, f"{subject} exam has no questions"
        for q in exam.questions:
            assert len(q.choices) >= 2
            assert 0 <= q.correct_index < len(q.choices)


# ---------------------------------------------------------------------------
# DB-backed: catalogue + timeline + idempotency
# ---------------------------------------------------------------------------
async def test_seed_catalogue_creates_real_lessons_and_exams(session):
    from app.models.exam import Exam, Question
    from app.models.learning import Course, Lesson

    teacher = await _teacher(session)
    await _roster(session, 2)
    await seed_timeline.seed_catalogue(session, [teacher])
    await session.flush()

    # Scope to the courses this seeder owns (deterministic ids derive from the
    # subject+class title), so other tests' rows never distort the assertions.
    expected_titles = {
        f"{subject} — Kelas {cls}"
        for cls, _ctype in content.CLASSES
        for subject in (
            ["B. Indonesia", "B. Inggris"]
            + (["Matematika", "Fisika", "Kimia", "Biologi"] if _ctype == "IPA" else ["Ekonomi", "Sosiologi", "Geografi", "Sejarah"])
        )
    }
    curriculum_ids = {det_uuid("course", t, t.split(" — Kelas ")[1]) for t in expected_titles}
    courses = list(
        (await session.execute(select(Course).where(Course.id.in_(curriculum_ids)))).scalars()
    )
    assert courses, "no curriculum courses created"
    titles = {c.title for c in courses}
    assert any(t.startswith("Matematika — Kelas") for t in titles)
    assert all("#" not in (c.description or "") for c in courses)

    lessons = list(
        (await session.execute(select(Lesson).where(Lesson.course_id.in_(curriculum_ids)))).scalars()
    )
    assert lessons
    # Lesson bodies are real markdown, not the old single placeholder line.
    assert any(
        "##" in (lesson.content_md or "") or "**" in (lesson.content_md or "")
        for lesson in lessons
    )

    exam_ids = {
        det_uuid("exam", content.exam_for(subject).title)
        for subject in content.subjects()
        if content.exam_for(subject) is not None
    }
    exams = list((await session.execute(select(Exam).where(Exam.id.in_(exam_ids)))).scalars())
    assert len(exams) == len(content.EXAM_BANK)
    for exam in exams:
        assert exam.status == "published"
        qs = list((await session.execute(select(Question).where(Question.exam_id == exam.id))).scalars())
        assert qs, f"exam {exam.title} has no questions"
        for q in qs:
            assert q.qtype == "multiple_choice"
            assert q.review_status == "approved"


async def test_seed_catalogue_is_idempotent(session):
    from app.models.exam import Exam
    from app.models.learning import Course, Lesson

    teacher = await _teacher(session, "tl_teacher_idem@ex.com")
    await _roster(session, 2)
    await seed_timeline.seed_catalogue(session, [teacher])
    await session.flush()
    first = (
        int((await session.execute(select(func.count()).select_from(Course))).scalar_one()),
        int((await session.execute(select(func.count()).select_from(Lesson))).scalar_one()),
        int((await session.execute(select(func.count()).select_from(Exam))).scalar_one()),
    )
    # Second pass: nothing new, nothing raised.
    await seed_timeline.seed_catalogue(session, [teacher])
    await session.flush()
    second = (
        int((await session.execute(select(func.count()).select_from(Course))).scalar_one()),
        int((await session.execute(select(func.count()).select_from(Lesson))).scalar_one()),
        int((await session.execute(select(func.count()).select_from(Exam))).scalar_one()),
    )
    assert first == second


async def test_timeline_produces_monthly_volume_and_spans_since_2025(session):
    """The heart of the requirement: 100–200 learning records every month."""
    from app.models.exam import ExamAttempt
    from app.models.learning import LessonProgress
    from app.models.quest import QuestAttempt

    teacher = await _teacher(session, "tl_teacher_vol@ex.com")
    students = await _roster(session, 40)
    await seed_timeline.seed_catalogue(session, [teacher])
    from app.db.seed_bulk import seed_tasks
    await seed_tasks(session, [teacher], students)
    await session.flush()

    # A couple of quests so quest entries are produced too.
    from app.models.exam import Exam
    from app.models.quest import Quest, QuestRule

    exam = (await session.execute(select(Exam).where(Exam.status == "published").limit(1))).scalar_one()
    for i in range(3):
        q = Quest(title=f"Timeline Quest {i}", owner_id=teacher.id, status="open", exam_id=exam.id)
        session.add(q)
        await session.flush()
        session.add(QuestRule(quest_id=q.id, rank=1, reward_amount=100))
    await session.flush()

    await seed_timeline.seed_activity_timeline(session)
    await session.flush()

    # Aggregate learning records per month across the whole timeline domain:
    # lesson progress + exam attempts + quest attempts + task completions.
    from app.models.quest import TaskCompletion

    counts: dict[tuple[int, int], int] = {}

    def _bump(mon, inc: int = 1) -> None:
        if mon is None:
            return
        key = (mon.year, mon.month)
        counts[key] = counts.get(key, 0) + inc

    for (mon,) in (await session.execute(select(LessonProgress.completed_at))).all():
        _bump(mon)
    for (mon,) in (await session.execute(select(ExamAttempt.submitted_at))).all():
        _bump(mon)
    for (mon,) in (await session.execute(select(QuestAttempt.submitted_at))).all():
        _bump(mon)
    for (mon,) in (await session.execute(select(TaskCompletion.completed_at))).all():
        _bump(mon)

    assert counts, "timeline produced no records"
    first_month = min(counts)
    assert first_month[0] == 2025, f"timeline starts at {first_month}, expected 2025"
    expected_months = seed_timeline.month_starts()
    assert len(counts) == len(expected_months), f"expected {len(expected_months)} months, got {len(counts)}"
    for (year, month), c in counts.items():
        assert 100 <= c <= 200, f"{year}-{month} out of range [100, 200]: {c}"

    # Every attempt for the seeded cohort is graded and tied to a real learner.
    student_ids = {s.id for s in students}
    attempts = list(
        (await session.execute(select(ExamAttempt).where(ExamAttempt.user_id.in_(student_ids)))).scalars()
    )
    assert attempts
    assert all(a.status == "graded" for a in attempts)
    assert all(a.score_bp is not None for a in attempts)
    # Quest entries exist and reference real students.
    qattempts = list(
        (await session.execute(select(QuestAttempt).where(QuestAttempt.user_id.in_(student_ids)))).scalars()
    )
    assert qattempts


async def test_timeline_is_idempotent(session):
    teacher = await _teacher(session, "tl_teacher_idem2@ex.com")
    await _roster(session, 6)
    await seed_timeline.seed_catalogue(session, [teacher])
    await session.flush()

    await seed_timeline.seed_activity_timeline(session)
    await session.flush()
    before = await _activity_count(session)
    # Re-run must not raise and must not add rows.
    await seed_timeline.seed_activity_timeline(session)
    await session.flush()
    after = await _activity_count(session)
    assert before == after


async def _activity_count(session) -> int:
    from app.models.exam import ExamAttempt
    from app.models.learning import LessonProgress
    from app.models.quest import QuestAttempt, TaskCompletion

    total = 0
    for model in (LessonProgress, ExamAttempt, QuestAttempt, TaskCompletion):
        total += int((await session.execute(select(func.count()).select_from(model))).scalar_one())
    return total


async def test_certificates_issue_on_course_completion(session):
    """A student who finishes every lesson of a course gets a certificate whose
    issued_at matches the completion month."""
    from app.models.certificate import Certificate
    from app.models.learning import Course, Lesson, LessonProgress

    teacher = await _teacher(session, "tl_teacher_cert@ex.com")
    students = await _roster(session, 1)
    await seed_timeline.seed_catalogue(session, [teacher])
    await session.flush()

    student = students[0]
    course = (
        await session.execute(
            select(Course)
            .where(Course.class_code == student.class_code, Course.owner_id == teacher.id)
            .limit(1)
        )
    ).scalar_one()
    lessons = list((await session.execute(select(Lesson).where(Lesson.course_id == course.id))).scalars())
    assert lessons, "seeded course must have lessons"
    when = datetime(2025, 3, 15, 10, 0, tzinfo=UTC)
    for lesson in lessons:
        session.add(
            LessonProgress(
                user_id=student.id,
                lesson_id=lesson.id,
                course_id=course.id,
                progress_percent=100,
                completed=True,
                completed_at=when,
            )
        )
    await session.flush()

    await seed_timeline.seed_certificates_timeline(session)
    await session.flush()

    cert = (
        await session.execute(
            select(Certificate).where(
                Certificate.user_id == student.id, Certificate.course_id == course.id
            )
        )
    ).scalar_one_or_none()
    assert cert is not None
    assert cert.issued_at.year == 2025 and cert.issued_at.month == 3
    assert cert.course_title == course.title
    assert cert.credential_id.startswith("QLT-")
