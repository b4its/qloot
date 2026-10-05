"""Time-distributed learning-activity seeder ("learning timeline").

The curated demo (``app.db.seed``) creates a handful of hand-crafted rows; the
bulk seeder (``app.db.seed_bulk``) pads the *catalogue* to a fixed size. Neither
produces a believable **history**: every attempt/progress row is stamped "now",
so dashboards, streaks and analytics look flat and the same age.

This module fixes that. It replays the real product flow — join class → read
lessons → sit exams → get graded → earn rewards/certificates — across a real
calendar, generating **100–200 learning-activity records per month starting
January 2025** and spreading them across the days/hours of each month.

What counts as a "learning record" (the monthly budget these all share):
  - ``lesson_progress``  (reading/finishing a lesson)
  - ``exam_attempts``    (sitting an exam — with student_answers + grading)
  - ``quest_attempts``   (entering a ranked competition)
  - ``task_completions`` (finishing a daily/learning/exam task)
  - ``certificates``     (finishing every lesson of a course)

Everything is deterministic (uuid5 ids derived from ``(kind, month, seq)``) and
idempotent (a row-count guard + stable ids), so re-running only fills the gaps
and never duplicates. Timestamps are derived from the month bucket, so the data
is internally consistent: an attempt's ``submitted_at`` always falls inside the
month it belongs to, and progress/certificates follow the attempts.
"""

from __future__ import annotations

import calendar
import random
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import content
from app.db.seed_bulk import det_uuid
from app.models.identity import User

log = get_logger("seed_timeline")

# The window starts here and runs to the first day of the current month.
START_YEAR = 2025
START_MONTH = 1

# Records generated per month, picked deterministically inside this range so
# every month carries a realistic, non-uniform load (100..200 inclusive).
MONTHLY_MIN = 100
MONTHLY_MAX = 200

# How the monthly budget is split across record kinds (weights, not counts).
KIND_WEIGHTS: dict[str, int] = {
    "lesson_progress": 40,
    "exam_attempt": 30,
    "task_completion": 18,
    "quest_attempt": 12,
}

# Class codes whose students we simulate (mirrors content.CLASSES).
CLASS_LOOKUP: dict[str, str] = dict(content.CLASSES)


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def month_starts(as_of: datetime | None = None) -> list[tuple[int, int]]:
    """Return every ``(year, month)`` from START up to (incl.) the current month."""
    now = as_of or datetime.now(UTC)
    out: list[tuple[int, int]] = []
    year, month = START_YEAR, START_MONTH
    while (year, month) <= (now.year, now.month):
        out.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


def monthly_volume(year: int, month: int) -> int:
    """Deterministic record count for a month, inside ``[100, 200]``.

    Uses a stable hash of the month so the same month always yields the same
    volume (idempotency) while different months vary.
    """
    rng = random.Random(f"vol:{year}-{month:02d}:{content.__doc__ is not None}")
    return rng.randint(MONTHLY_MIN, MONTHLY_MAX)


def _random_datetime_in_month(rng: random.Random, year: int, month: int) -> datetime:
    """A believable timestamp inside the month (weekday, 07:00–21:00 WIB-ish UTC)."""
    days = calendar.monthrange(year, month)[1]
    day = rng.randint(1, days)
    hour = rng.choice([7, 8, 9, 13, 14, 15, 16, 19, 20])
    minute = rng.randint(0, 59)
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _split_budget(total: int, rng: random.Random) -> dict[str, int]:
    """Distribute ``total`` records across kinds by weight (remainder to largest)."""
    weight_sum = sum(KIND_WEIGHTS.values())
    counts = {kind: total * weight // weight_sum for kind, weight in KIND_WEIGHTS.items()}
    remainder = total - sum(counts.values())
    # Hand the remainder to lesson_progress (the most common kind).
    counts["lesson_progress"] += remainder
    # A tiny deterministic jitter so the split is not perfectly proportional.
    if total > 20:
        shift = rng.randint(0, 3)
        counts["exam_attempt"] += shift
        counts["lesson_progress"] = max(0, counts["lesson_progress"] - shift)
    return counts


# ---------------------------------------------------------------------------
# Catalogue: ensure each subject has courses, lessons, exams, questions
# ---------------------------------------------------------------------------
async def seed_catalogue(session: AsyncSession, teachers: list[User]) -> None:
    """Create realistic subjects/lessons/exams/questions per (class, subject).

    Replaces the old ``SUBJECTS[i % n] — Kelas X #001`` filler with the real
    curriculum in :mod:`app.db.content`. Idempotent per (title, class_code).
    """
    from app.models.exam import Exam, Question, QuestionOption
    from app.models.learning import Course, Lesson

    if not teachers:
        return

    # One course per (class, subject). 6 classes x up to 10 subjects.
    existing_courses = {
        (title, cls): cid
        for title, cls, cid in (
            await session.execute(select(Course.title, Course.class_code, Course.id))
        ).all()
    }
    existing_lessons = {lid for (lid,) in (await session.execute(select(Lesson.id))).all()}
    created_courses = 0
    for ci, (cls_code, _cls_type) in enumerate(content.CLASSES):
        # IPA classes take the science set, IPS the social set, plus shared cores.
        cls_type = CLASS_LOOKUP[cls_code]
        science = ["Matematika", "Fisika", "Kimia", "Biologi"]
        social = ["Ekonomi", "Sosiologi", "Geografi", "Sejarah"]
        shared = ["B. Indonesia", "B. Inggris"]
        subject_list = shared + (science if cls_type == "IPA" else social)
        for si, subject in enumerate(subject_list):
            title = f"{subject} — Kelas {cls_code}"
            key = (title, cls_code)
            if key in existing_courses:
                course_id = existing_courses[key]
            else:
                owner = teachers[(ci + si) % len(teachers)]
                course_id = det_uuid("course", title, cls_code)
                slug_subject = subject.lower().replace(" ", "-").replace(".", "")
                session.add(
                    Course(
                        id=course_id,
                        title=title,
                        slug=f"{slug_subject}-{cls_code.lower()}",
                        description=(
                            f"{subject} untuk kelas {cls_code} ({cls_type}). "
                            f"Kurikulum merdeka, fokus pemahaman konsep dan latihan soal."
                        ),
                        owner_id=owner.id,
                        is_published=True,
                        class_code=cls_code,
                        class_type=cls_type,
                        subject=subject,
                    )
                )
                existing_courses[key] = course_id
                created_courses += 1

            # Lessons for this subject (shared bank across classes).
            lessons = content.lessons_for(subject)
            for pos, spec in enumerate(lessons):
                lesson_id = det_uuid("lesson", str(course_id), spec.title)
                if lesson_id in existing_lessons:
                    continue
                existing_lessons.add(lesson_id)
                session.add(
                    Lesson(
                        id=lesson_id,
                        course_id=course_id,
                        title=spec.title,
                        content_md=spec.body,
                        position=pos,
                        is_published=True,
                    )
                )
    await session.flush()

    # Exams: one per subject (attached to that subject's first class course).
    existing_exams = {t for (t,) in (await session.execute(select(Exam.title))).all()}
    for ei, subject in enumerate(content.subjects()):
        exam_spec = content.exam_for(subject)
        if exam_spec is None or exam_spec.title in existing_exams:
            continue
        owner = teachers[ei % len(teachers)]
        # Attach to a matching course when we can find one.
        course = (
            await session.execute(
                select(Course).where(Course.subject == subject).order_by(Course.class_code).limit(1)
            )
        ).scalar_one_or_none()
        exam_id = det_uuid("exam", exam_spec.title)
        session.add(
            Exam(
                id=exam_id,
                title=exam_spec.title,
                owner_id=owner.id,
                course_id=course.id if course else None,
                duration_minutes=exam_spec.duration_minutes,
                status="published",
                is_active=True,
                passing_score_bp=exam_spec.passing_score_bp,
                instructions=exam_spec.instructions,
                max_attempts=2,
            )
        )
        await session.flush()
        labels = "ABCDEFGH"
        for pos, q in enumerate(exam_spec.questions):
            qid = det_uuid("question", exam_spec.title, str(pos))
            session.add(
                Question(
                    id=qid,
                    exam_id=exam_id,
                    owner_id=owner.id,
                    prompt=q.prompt,
                    correct_answer=labels[q.correct_index],
                    qtype="multiple_choice",
                    position=pos,
                    source="manual",
                    review_status="approved",
                )
            )
            await session.flush()
            for oi, text in enumerate(q.choices):
                session.add(
                    QuestionOption(
                        id=det_uuid("qopt", str(qid), labels[oi]),
                        question_id=qid,
                        label=labels[oi],
                        text=text,
                        is_correct=(oi == q.correct_index),
                        position=oi,
                    )
                )
        await session.flush()
    log.info("timeline_catalogue_ready", courses=created_courses)


# ---------------------------------------------------------------------------
# Pick helpers
# ---------------------------------------------------------------------------
async def _load_roster(session: AsyncSession) -> tuple[list[User], dict[str, list[User]]]:
    """Students grouped by class_code, plus the flat roster."""
    students = list(
        (await session.execute(select(User).where(User.email.like("student%@qloot.example"))))
        .scalars()
        .all()
    )
    by_class: dict[str, list[User]] = {}
    for s in students:
        by_class.setdefault((s.class_code or "UMUM").upper(), []).append(s)
    return students, by_class


# ---------------------------------------------------------------------------
# Monthly activity generation
# ---------------------------------------------------------------------------
async def seed_activity_timeline(session: AsyncSession) -> None:
    """Generate the monthly learning history across the whole window.

    Volume-driven: for each month we target ``monthly_volume(year, month)``
    learning records (100–200) and pull from a rotating set of generators until
    the budget is met. Generators that can repeat across months (exam attempts,
    task completions, quest entries, proctoring events) guarantee the floor even
    once a student has already completed every unique lesson.
    """
    from app.models.exam import AttemptEvent, Exam, ExamAttempt
    from app.models.learning import Course, Lesson, LessonProgress
    from app.models.quest import Quest, QuestAttempt, TaskCompletion

    students, by_class = await _load_roster(session)
    if not students:
        log.warning("timeline_no_students")
        return

    courses = list((await session.execute(select(Course))).scalars().all())
    lessons = list((await session.execute(select(Lesson))).scalars().all())
    exams = list(
        (await session.execute(select(Exam).where(Exam.status == "published"))).scalars().all()
    )
    if not courses or not lessons or not exams:
        log.warning("timeline_no_catalogue")
        return

    lessons_by_course: dict[uuid.UUID, list[Lesson]] = {}
    for lesson in lessons:
        lessons_by_course.setdefault(lesson.course_id, []).append(lesson)
    for bucket in lessons_by_course.values():
        bucket.sort(key=lambda lesson: lesson.position)
    lessons_by_class: dict[str, list[Lesson]] = {}
    for course in courses:
        cc = (course.class_code or "UMUM").upper()
        lessons_by_class.setdefault(cc, []).extend(lessons_by_course.get(course.id, []))

    quests = list(
        (await session.execute(select(Quest).where(Quest.status == "open"))).scalars().all()
    )

    # Track unique keys so we never violate the schema constraints even if the
    # DB already has rows from a prior run.
    existing_lp = {
        (p.user_id, p.lesson_id) for p in (await session.execute(select(LessonProgress))).scalars()
    }
    existing_attempt = {
        (a.exam_id, a.user_id, a.attempt_number)
        for a in (await session.execute(select(ExamAttempt))).scalars()
    }
    existing_quest = {
        (q.quest_id, q.user_id) for q in (await session.execute(select(QuestAttempt))).scalars()
    }
    existing_tc: set[tuple[uuid.UUID, uuid.UUID, str]] = {
        (t.task_id, t.user_id, t.period_key)
        for t in (await session.execute(select(TaskCompletion))).scalars()
    }
    from app.models.quest import Task as _Task

    tasks = list(
        (await session.execute(select(_Task).where(_Task.is_active.is_(True)))).scalars().all()
    )
    exam_attempts = list((await session.execute(select(ExamAttempt))).scalars().all())
    existing_events = {eid for (eid,) in (await session.execute(select(AttemptEvent.id))).all()}

    existing_by_month: dict[tuple[int, int], int] = {}

    def _tally(dt: datetime | None) -> None:
        if dt is not None:
            key = (dt.year, dt.month)
            existing_by_month[key] = existing_by_month.get(key, 0) + 1

    for dt in (await session.execute(select(LessonProgress.completed_at))).scalars():
        _tally(dt)
    for dt in (await session.execute(select(ExamAttempt.submitted_at))).scalars():
        _tally(dt)
    for dt in (await session.execute(select(QuestAttempt.submitted_at))).scalars():
        _tally(dt)
    for dt in (await session.execute(select(TaskCompletion.completed_at))).scalars():
        _tally(dt)

    ctx = _MonthContext(
        students=students,
        by_class=by_class,
        lessons_by_class=lessons_by_class,
        exams=exams,
        quests=quests,
        tasks=tasks,
        exam_attempts=exam_attempts,
        existing_lp=existing_lp,
        existing_attempt=existing_attempt,
        existing_quest=existing_quest,
        existing_tc=existing_tc,
        existing_events=existing_events,
        existing_by_month=existing_by_month,
    )

    total_records = 0
    for year, month in month_starts():
        made = await _seed_month(session, year=year, month=month, ctx=ctx)
        total_records += made
        log.info("timeline_month", year=year, month=month, records=made)

    await session.flush()
    log.info("timeline_activity_ready", months=len(month_starts()), records=total_records)


@dataclass
class _MonthContext:
    """Mutable cross-month state so unique keys survive between months."""

    students: list
    by_class: dict
    lessons_by_class: dict
    exams: list
    quests: list
    tasks: list
    exam_attempts: list
    existing_lp: set
    existing_attempt: set
    existing_quest: set
    existing_tc: set
    existing_events: set
    existing_by_month: dict = field(default_factory=dict)
    # Per-month deterministic RNG + counter, set by ``_seed_month``.
    rng: random.Random | None = None
    _slot: int = 0

    def record_made(self, year: int, month: int, inc: int = 1) -> None:
        key = (year, month)
        self.existing_by_month[key] = self.existing_by_month.get(key, 0) + inc

    def reset_month(self, rng: random.Random) -> None:
        self.rng = rng
        self._slot = 0

    def time_in_month(self, year: int, month: int) -> datetime:
        """Deterministic timestamp inside the month for the next planned row."""
        slot = self._slot
        self._slot += 1
        days = calendar.monthrange(year, month)[1]
        day = 1 + (slot * 7 + (slot // days)) % days
        hour = [7, 8, 9, 13, 14, 15, 16, 19, 20][slot % 9]
        minute = (slot * 13) % 60
        return datetime(year, month, day, hour, minute, tzinfo=UTC)

    def duration_for(self, exam) -> int:
        return 600 + ((self._slot * 137) % max(1, exam.duration_minutes * 60 - 600))

    def score_for(self, key: tuple) -> int:
        bucket = hash(str(key)) % 100
        if bucket < 62:
            return 7000 + (hash(str(key)) % 2800)
        if bucket < 85:
            return 5500 + (hash(str(key)) % 1499)
        return 3000 + (hash(str(key)) % 2499)

    def pick(self, options: list[str]) -> str:
        assert self.rng is not None
        return self.rng.choice(options)


async def _seed_month(session: AsyncSession, *, year: int, month: int, ctx: _MonthContext) -> int:
    """Generate exactly one month's budget of learning records."""
    volume = monthly_volume(year, month)
    already = ctx.existing_by_month.get((year, month), 0)
    needed = max(0, volume - already)
    if needed == 0:
        return 0

    rng = random.Random(f"month:{year}-{month:02d}")
    ctx.reset_month(rng)

    plan = _build_plan(year=year, month=month, rng=rng, ctx=ctx)

    made = 0
    for item in plan:
        if made >= needed:
            break
        inc = await item.run(session, ctx=ctx)
        made += inc
        if inc > 0:
            ctx.record_made(year, month, inc)
        if made % 50 == 0:
            await session.flush()

    await session.flush()
    return made


@dataclass
class _PlanItem:
    """One unit of planned activity: a kind + the key that makes it unique."""

    kind: str
    run: Callable[..., Awaitable[int]]


def _build_plan(
    *, year: int, month: int, rng: random.Random, ctx: _MonthContext
) -> list[_PlanItem]:
    """Deterministically plan a month's records in a realistic kind mix.

    Candidates are generated per kind, weighted to look like the real flow, then
    interleaved via a shuffled draw so the *order* (and thus which land inside a
    partial month budget) is stable across runs.
    """
    from functools import partial

    items: list[_PlanItem] = []

    # lesson_progress candidates: every (student, lesson) not yet taken.
    for student in ctx.students:
        pool = ctx.lessons_by_class.get((student.class_code or "UMUM").upper()) or []
        for lesson in pool:
            key = (student.id, lesson.id)
            if key in ctx.existing_lp:
                continue
            items.append(
                _PlanItem(
                    "lesson",
                    partial(
                        _emit_lesson_progress,
                        student=student,
                        lesson=lesson,
                        year=year,
                        month=month,
                    ),
                )
            )

    # exam_attempt candidates: every (exam, student, attempt_no) not yet taken.
    for exam in ctx.exams:
        for student in ctx.students:
            for attempt_no in (1, 2):
                if (exam.id, student.id, attempt_no) in ctx.existing_attempt:
                    continue
                items.append(
                    _PlanItem(
                        "exam",
                        partial(
                            _emit_exam_attempt,
                            exam=exam,
                            student=student,
                            attempt_no=attempt_no,
                            year=year,
                            month=month,
                        ),
                    )
                )

    # task_completion candidates.
    for task in ctx.tasks:
        if task.kind == "daily":
            for day_offset in (5, 12, 19, 26):
                period = f"{year}-{month:02d}-{day_offset:02d}"
                for student in ctx.students:
                    if (task.id, student.id, period) in ctx.existing_tc:
                        continue
                    items.append(
                        _PlanItem(
                            "task",
                            partial(
                                _emit_task_completion,
                                task=task,
                                student=student,
                                period=period,
                                year=year,
                                month=month,
                            ),
                        )
                    )
        else:
            period = ""
            for student in ctx.students:
                if (task.id, student.id, period) in ctx.existing_tc:
                    continue
                items.append(
                    _PlanItem(
                        "task",
                        partial(
                            _emit_task_completion,
                            task=task,
                            student=student,
                            period=period,
                            year=year,
                            month=month,
                        ),
                    )
                )

    # quest_attempt candidates.
    for quest in ctx.quests:
        for student in ctx.students:
            if (quest.id, student.id) in ctx.existing_quest:
                continue
            items.append(
                _PlanItem(
                    "quest",
                    partial(
                        _emit_quest_attempt, quest=quest, student=student, year=year, month=month
                    ),
                )
            )

    rng.shuffle(items)
    return items


# ---------------------------------------------------------------------------
# Individual record emitters (one planned activity each)
# ---------------------------------------------------------------------------
async def _emit_lesson_progress(
    session: AsyncSession, *, ctx: _MonthContext, student, lesson, year: int, month: int
) -> int:
    from app.models.learning import LessonProgress

    key = (student.id, lesson.id)
    if key in ctx.existing_lp:
        return 0
    ctx.existing_lp.add(key)
    done_at = ctx.time_in_month(year, month)
    session.add(
        LessonProgress(
            id=det_uuid("lprog", str(student.id), str(lesson.id)),
            user_id=student.id,
            lesson_id=lesson.id,
            course_id=lesson.course_id,
            progress_percent=100,
            completed=True,
            completed_at=done_at,
            updated_at=done_at,
        )
    )
    return 1


async def _emit_exam_attempt(
    session: AsyncSession,
    *,
    ctx: _MonthContext,
    exam,
    student,
    attempt_no: int,
    year: int,
    month: int,
) -> int:
    from app.models.exam import AttemptEvent, ExamAttempt, Question, StudentAnswer

    key = (exam.id, student.id, attempt_no)
    if key in ctx.existing_attempt:
        return 0
    ctx.existing_attempt.add(key)
    submitted = ctx.time_in_month(year, month)
    duration = ctx.duration_for(exam)
    started = submitted - timedelta(seconds=duration)
    score = ctx.score_for(key)
    attempt_id = det_uuid(
        "attempt", str(exam.id), str(student.id), str(attempt_no), str(year), str(month)
    )
    attempt = ExamAttempt(
        id=attempt_id,
        exam_id=exam.id,
        user_id=student.id,
        attempt_number=attempt_no,
        status="graded",
        score_bp=score,
        passed=score >= exam.passing_score_bp,
        started_at=started,
        submitted_at=submitted,
        graded_at=submitted + timedelta(minutes=2),
        duration_seconds=duration,
        expires_at=started + timedelta(minutes=exam.duration_minutes),
    )
    session.add(attempt)
    await session.flush()

    # Deterministic proctoring telemetry: ids derive from the attempt id, so
    # re-runs reproduce exactly the same events (idempotent).
    n_events = 1 + (hash(str(attempt_id)) % 3)
    for ei in range(n_events):
        event_id = det_uuid("aevent", str(attempt_id), str(ei))
        if event_id in ctx.existing_events:
            continue
        ctx.existing_events.add(event_id)
        session.add(
            AttemptEvent(
                id=event_id,
                attempt_id=attempt_id,
                kind=ctx.pick(["blur", "visibility_hidden", "focus", "dwell", "paste"]),
                detail={"seconds": 1 + (hash(event_id.hex) % 45)},
                created_at=submitted - timedelta(seconds=10 + (hash(event_id.hex) % duration)),
            )
        )

    questions = list(
        (
            await session.execute(
                select(Question).where(Question.exam_id == exam.id).order_by(Question.position)
            )
        )
        .scalars()
        .all()
    )
    for qi, q in enumerate(questions):
        session.add(
            StudentAnswer(
                id=det_uuid("sanswer", str(attempt_id), str(q.id)),
                attempt_id=attempt_id,
                question_id=q.id,
                answer_text="Jawaban siswa.",
                score_bp=score if qi == 0 else max(0, score - qi * 400),
                max_score_bp=q.max_score_bp,
                feedback="Dinilai otomatis oleh QLoot AI.",
                similarity_bp=score,
                graded_at=submitted + timedelta(minutes=2),
            )
        )
    return 1


async def _emit_task_completion(
    session: AsyncSession, *, ctx: _MonthContext, task, student, period: str, year: int, month: int
) -> int:
    from app.models.quest import TaskCompletion
    from app.services.keys import task_reward_key

    tc_key = (task.id, student.id, period)
    if tc_key in ctx.existing_tc:
        return 0
    ctx.existing_tc.add(tc_key)
    done_at = ctx.time_in_month(year, month)
    session.add(
        TaskCompletion(
            id=det_uuid("tcomp", str(task.id), str(student.id), period or f"{year}-{month:02d}"),
            task_id=task.id,
            user_id=student.id,
            period_key=period,
            reward_key=task_reward_key(task.id, student.id, period),
            completed_at=done_at,
        )
    )
    return 1


async def _emit_quest_attempt(
    session: AsyncSession, *, ctx: _MonthContext, quest, student, year: int, month: int
) -> int:
    from app.models.quest import QuestAttempt

    key = (quest.id, student.id)
    if key in ctx.existing_quest:
        return 0
    ctx.existing_quest.add(key)
    submitted = ctx.time_in_month(year, month)
    session.add(
        QuestAttempt(
            id=det_uuid("qattempt", str(quest.id), str(student.id)),
            quest_id=quest.id,
            user_id=student.id,
            exam_attempt_id=None,
            submitted_at=submitted,
            score_bp=ctx.score_for(key),
            is_valid=True,
        )
    )
    return 1


# ---------------------------------------------------------------------------
# Certificates (flow terminus): a student who completed every lesson of a
# course gets a certificate dated in the month they finished.
# ---------------------------------------------------------------------------
async def seed_certificates_timeline(session: AsyncSession) -> None:
    """Issue certificates for fully-completed courses, dated at completion."""
    from app.models.certificate import Certificate
    from app.models.learning import Course, Lesson, LessonProgress
    from app.services.certificate_service import _prefix_from_title, _verification_hash

    existing = {
        (c.user_id, c.course_id) for c in (await session.execute(select(Certificate))).scalars()
    }
    courses = list((await session.execute(select(Course))).scalars().all())
    lesson_by_course: dict[uuid.UUID, set[uuid.UUID]] = {}
    for lesson in (await session.execute(select(Lesson))).scalars():
        lesson_by_course.setdefault(lesson.course_id, set()).add(lesson.id)

    # Ensure demo students complete their primary course lessons so certificates exist.
    demo_course = courses[0] if courses else None
    if demo_course and demo_course.id in lesson_by_course:
        demo_lessons = list(
            (
                await session.execute(
                    select(Lesson)
                    .where(Lesson.course_id == demo_course.id)
                    .order_by(Lesson.position)
                )
            )
            .scalars()
            .all()
        )
        students = list(
            (
                await session.execute(
                    select(User).where(User.email.like("student%@qloot.example")).limit(3)
                )
            )
            .scalars()
            .all()
        )
        for s in students:
            for li, lesson in enumerate(demo_lessons):
                exists = (
                    await session.execute(
                        select(LessonProgress).where(
                            LessonProgress.user_id == s.id, LessonProgress.lesson_id == lesson.id
                        )
                    )
                ).scalar_one_or_none()
                done_time = datetime(2025, 3, 10 + li, 14, 0, tzinfo=UTC)
                if exists is None:
                    p = LessonProgress(
                        id=det_uuid("lprog", str(s.id), str(lesson.id)),
                        user_id=s.id,
                        lesson_id=lesson.id,
                        course_id=demo_course.id,
                        progress_percent=100,
                        completed=True,
                        completed_at=done_time,
                        updated_at=done_time,
                    )
                    session.add(p)
                else:
                    exists.completed = True
                    exists.progress_percent = 100
                    exists.completed_at = done_time
        await session.flush()

    # All completed progress rows, grouped by (user, course).
    progress_rows = list(
        (await session.execute(select(LessonProgress).where(LessonProgress.completed.is_(True))))
        .scalars()
        .all()
    )
    done_by_user_course: dict[tuple[uuid.UUID, uuid.UUID], list[LessonProgress]] = {}
    for p in progress_rows:
        done_by_user_course.setdefault((p.user_id, p.course_id), []).append(p)

    edition = int(
        (await session.execute(select(func.count()).select_from(Certificate))).scalar_one()
    )
    created = 0
    for course in courses:
        needed = lesson_by_course.get(course.id, set())
        if not needed:
            continue
        for (user_id, course_id), rows in done_by_user_course.items():
            if course_id != course.id:
                continue
            if (user_id, course_id) in existing:
                continue
            if {r.lesson_id for r in rows} != needed:
                continue
            finished_at = max(
                (r.completed_at for r in rows if r.completed_at),
                default=None,
            )
            if finished_at is None:
                continue
            edition += 1
            prefix = _prefix_from_title(course.title)
            suffix = uuid.uuid5(uuid.NAMESPACE_URL, f"{user_id}{course_id}").hex[:6].upper()
            credential_id = f"QLT-{prefix}-{edition:04d}-{suffix}"
            session.add(
                Certificate(
                    id=det_uuid("cert", str(user_id), str(course_id)),
                    user_id=user_id,
                    course_id=course_id,
                    credential_id=credential_id,
                    verification_hash=_verification_hash(credential_id),
                    course_title=course.title,
                    recipient_name=await _full_name(session, user_id),
                    issued_by="QLoot Academy",
                    edition_number=edition,
                    edition_total=5000,
                    issued_at=finished_at,
                )
            )
            existing.add((user_id, course_id))
            created += 1
    await session.flush()
    log.info("timeline_certificates_ready", created=created)


async def _full_name(session: AsyncSession, user_id: uuid.UUID) -> str:
    name = (
        await session.execute(select(User.full_name).where(User.id == user_id))
    ).scalar_one_or_none()
    return name or "Siswa QLoot"


# ---------------------------------------------------------------------------
# Entry point (called by seed.py after the curated demo)
# ---------------------------------------------------------------------------
async def main(teachers: list[User] | None = None) -> None:
    """Run the whole timeline seed against the current DB session_scope."""
    from app.db.session import session_scope

    async with session_scope() as session:
        if teachers is None:
            teachers = list(
                (
                    await session.execute(
                        select(User).where(User.email.like("teacher%@qloot.example"))
                    )
                )
                .scalars()
                .all()
            )
        await seed_catalogue(session, teachers)
        await seed_activity_timeline(session)
        await seed_certificates_timeline(session)


def months_spanned(as_of: datetime | None = None) -> Iterator[tuple[int, int]]:
    yield from month_starts(as_of)
