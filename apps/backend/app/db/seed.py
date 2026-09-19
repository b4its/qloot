"""Seed a rich simulated QLoot environment.

Creates (idempotently):
  - roles, an admin, teachers and students
  - the badge catalog
  - published courses with lessons and PDF materials
  - exams with AI-generated (mock) questions, published
  - open rooms with members
  - quests with reward rules, and finalized winners with OPC rewards
  - tasks and some completions
  - ledger rewards + notifications + badges for simulated students

Run with: `python -m app.db.seed`.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope
from app.models.identity import Role, User
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.course_service import CourseService
from app.services.exam_service import ExamService
from app.services.quest_service import QuestService
from app.services.room_service import RoomService
from app.services.social_service import BadgeService
from app.services.storage import build_key, sniff_pdf, storage

log = get_logger("seed")

ROLES = [
    ("student", "Learner who takes quests and earns OPC"),
    ("teacher", "Creates materials, exams, rooms and quests"),
    ("admin", "Platform administrator"),
]

PASSWORD_BY_ROLE = {
    "admin": "AdminPass123!",
    "teacher": "TeacherPass123!",
    "student": "StudentPass123!",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _ensure_roles() -> None:
    async with session_scope() as session:
        for name, desc in ROLES:
            existing = (
                await session.execute(select(Role).where(Role.name == name))
            ).scalar_one_or_none()
            if existing is None:
                session.add(Role(name=name, description=desc))


async def _ensure_user(email: str, full_name: str, role: str) -> User:
    async with session_scope() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(email)
        if existing is not None:
            return existing
        auth = AuthService(session)
        user, _ = await auth.register(
            email=email,
            full_name=full_name,
            password=PASSWORD_BY_ROLE[role],
            role=role,
        )
        log.info("seed_user_created", email=email, role=role)
        return user


def _minimal_pdf(text: str) -> bytes:
    stream = b"BT /F1 12 Tf 72 720 Td (" + text.encode("latin-1", "ignore") + b") Tj ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += b"trailer << /Root 1 0 R /Size %d >>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        xref,
    )
    return bytes(out)


async def _seed_material(session, owner: User, filename: str, text: str):
    from app.models.learning import LearningMaterial
    from app.services.storage import sha256_hex

    existing = (
        await session.execute(
            select(LearningMaterial).where(
                LearningMaterial.owner_id == owner.id, LearningMaterial.filename == filename
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    data = _minimal_pdf(text)
    if not sniff_pdf(data):
        raise RuntimeError("seed pdf invalid")
    key = build_key(owner.id, filename)
    storage.put(key, data, "application/pdf")
    material = LearningMaterial(
        owner_id=owner.id,
        filename=filename,
        content_type="application/pdf",
        size_bytes=len(data),
        checksum_sha256=sha256_hex(data),
        storage_key=key,
        extracted_text=text,
        status="ready",
    )
    session.add(material)
    await session.flush()
    return material


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
async def main() -> None:
    configure_logging()
    await _ensure_roles()

    async with session_scope() as session:
        await BadgeService(session).ensure_catalog()

    admin = await _ensure_user("admin@qloot.example", "QLoot Admin", "admin")
    teacher = await _ensure_user("teacher@qloot.example", "Budi Guru", "teacher")
    teacher2 = await _ensure_user("teacher2@qloot.example", "Sari Guru", "teacher")
    students = [
        await _ensure_user(f"student{i}@qloot.example", f"Siswa {i}", "student")
        for i in range(1, 6)
    ]

    # --- courses, lessons, materials --------------------------------------
    async with session_scope() as session:
        from app.models.learning import Course, Lesson

        course = (
            await session.execute(select(Course).where(Course.slug == "dasar-pemrograman"))
        ).scalar_one_or_none()
        if course is None:
            svc = CourseService(session)
            course = await svc.create(
                teacher,
                title="Dasar Pemrograman",
                description="Pengantar konsep dasar pemrograman dan logika.",
                is_published=True,
            )
            log.info("seed_course_created", course=str(course.id))

        # Ensure all lessons exist individually (idempotent per lesson).
        lesson_specs = [
            ("Pengenalan Variabel", "# Variabel\nVariabel adalah wadah untuk menyimpan nilai."),
            ("Struktur Kontrol", "# Struktur Kontrol\nIf, else, dan loop mengatur alur program."),
            ("Fungsi", "# Fungsi\nFungsi mengelompokkan kode yang dapat dipakai ulang."),
        ]
        existing_lessons = {
            lesson.title
            for lesson in (
                await session.execute(select(Lesson).where(Lesson.course_id == course.id))
            )
            .scalars()
            .all()
        }
        for pos, (title, body) in enumerate(lesson_specs):
            if title in existing_lessons:
                continue
            await CourseService(session).add_lesson(
                course.id, teacher, title=title, content_md=body, position=pos, is_published=True
            )
        await session.flush()

        # Materials owned by the teacher.
        mat1 = await _seed_material(
            session,
            teacher,
            "materi-pemrograman.pdf",
            "Pemrograman adalah proses menulis instruksi. Variabel menyimpan nilai. "
            "Fungsi mengelompokkan kode. Algoritma adalah urutan langkah penyelesaian masalah.",
        )
        await _seed_material(
            session,
            teacher2,
            "materi-ai.pdf",
            "Kecerdasan buatan mempelajari agen cerdas. Pembelajaran mesin adalah cabangnya. "
            "Model dilatih menggunakan data berlabel.",
        )
        await session.flush()
        course_id = course.id
        mat1_id = mat1.id

    # --- exam + quest (published) -----------------------------------------
    async with session_scope() as session:
        from app.models.exam import Exam, Question
        from app.models.quest import Quest

        exam = (
            await session.execute(select(Exam).where(Exam.title == "Ujian Simulasi Dasar"))
        ).scalar_one_or_none()
        if exam is None:
            esvc = ExamService(session)
            exam = await esvc.create(
                teacher,
                title="Ujian Simulasi Dasar",
                duration_minutes=45,
                passing_score_bp=6000,
                course_id=course_id,
                instructions="Jawab dengan ringkas dan jelas.",
            )
            for i, (prompt, answer) in enumerate(
                [
                    ("Apa itu variabel dalam pemrograman?", "Wadah untuk menyimpan nilai."),
                    ("Apa fungsi algoritma?", "Urutan langkah menyelesaikan masalah."),
                    ("Mengapa fungsi penting?", "Agar kode dapat dipakai ulang."),
                ]
            ):
                session.add(
                    Question(
                        exam_id=exam.id,
                        owner_id=teacher.id,
                        material_id=mat1_id,
                        prompt=prompt,
                        correct_answer=answer,
                        position=i,
                        source="ai",
                        review_status="approved",
                    )
                )
            await session.flush()
            await esvc.publish(exam.id, teacher)
            log.info("seed_exam_created", exam=str(exam.id))

        quest = (
            await session.execute(select(Quest).where(Quest.title == "Quest Simulasi Cepat"))
        ).scalar_one_or_none()
        if quest is None:
            qsvc = QuestService(session)
            quest = await qsvc.create(
                teacher,
                [
                    {"rank": 1, "reward_amount": 100},
                    {"rank": 2, "reward_amount": 60},
                    {"rank": 3, "reward_amount": 40},
                ],
                title="Quest Simulasi Cepat",
                description="Selesaikan ujian secepat mungkin dengan nilai terbaik.",
                exam_id=exam.id,
                top_n_winners=3,
                status="open",
            )
            await session.flush()
            log.info("seed_quest_created", quest=str(quest.id))

    # --- room + members ---------------------------------------------------
    async with session_scope() as session:
        from app.models.room import Room

        room = (
            await session.execute(select(Room).where(Room.name == "Ruang Simulasi"))
        ).scalar_one_or_none()
        if room is None:
            rsvc = RoomService(session)
            room = await rsvc.create(
                teacher, name="Ruang Simulasi", max_participants=50, is_public=True
            )
            await rsvc.open(room.id, teacher)
            for s in students[:3]:
                await rsvc.join(room.id, s)
            log.info("seed_room_created", room=str(room.id))

    # --- tasks ------------------------------------------------------------
    async with session_scope() as session:
        from app.models.quest import Task

        existing = (
            await session.execute(select(Task).where(Task.title == "Baca 1 Materi"))
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Task(
                    title="Baca 1 Materi",
                    description="Selesaikan membaca satu materi pembelajaran.",
                    kind="learning",
                    reward_amount=10,
                    owner_id=teacher.id,
                    is_active=True,
                )
            )
            session.add(
                Task(
                    title="Ikut 1 Ruang",
                    description="Bergabung ke satu ruang kompetisi.",
                    kind="daily",
                    reward_amount=5,
                    owner_id=teacher.id,
                    is_active=True,
                )
            )
            await session.flush()
            log.info("seed_tasks_created")

    # --- simulate student activity: attempts, grading, rewards -------------
    await _simulate_activity(teacher, students)

    # --- simulate career guidance data -------------------------------------
    await _simulate_career(students)

    log.info(
        "seed_done",
        admin=str(admin.id),
        teacher=str(teacher.id),
        students=len(students),
    )


async def _simulate_career(students: list[User]) -> None:
    """Seed grades, personality, recommendations, roadmap and BK sessions."""
    from app.services.career_service import CareerService

    grade_sets = [
        {"Fisika": 92, "Matematika": 85, "Kimia": 64, "B. Inggris": 78, "B. Indonesia": 88},
        {"Fisika": 78, "Matematika": 90, "Kimia": 72, "B. Inggris": 82, "B. Indonesia": 80},
        {"Fisika": 70, "Matematika": 68, "Kimia": 85, "Biologi": 90, "B. Inggris": 76},
    ]
    answers = [5, 5, 3, 4, 2] * 6

    async with session_scope() as session:
        svc = CareerService(session)
        await svc.ensure_resources()
        for student, grades in zip(students[:3], grade_sets, strict=False):
            existing = await svc.list_grades(student.id)
            if existing:
                continue
            for subject, grade in grades.items():
                await svc.upsert_grade(student.id, subject, grade, "2025/2026-genap")
            await svc.score_personality(student, answers)
            await svc.generate_recommendations(student)
            await svc.create_consultation(
                student,
                counselor="Bu Ratna Wijaya",
                topic="Konsultasi Pemilihan Jurusan",
                notes="Diskusi hasil analisis AI.",
            )
            log.info("seed_career_student", student=str(student.id))

        # Approve + activate roadmap for the first student.
        first = students[0]
        if not await svc.list_milestones(first.id):
            await svc.approve(first)
            log.info("seed_career_roadmap_activated", student=str(first.id))


async def _simulate_activity(teacher: User, students: list[User]) -> None:
    """Simulate a graded exam + finalized quest with rewards and badges."""
    from sqlalchemy import func

    from app.models.exam import Exam, ExamAttempt, StudentAnswer
    from app.models.quest import Quest
    from app.models.wallet import RewardAllocation

    async with session_scope() as session:
        exam = (
            await session.execute(select(Exam).where(Exam.title == "Ujian Simulasi Dasar"))
        ).scalar_one_or_none()
        quest = (
            await session.execute(select(Quest).where(Quest.title == "Quest Simulasi Cepat"))
        ).scalar_one_or_none()
        if exam is None or quest is None:
            return

        # Skip if we've already simulated activity for this quest.
        existing_winners = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(RewardAllocation)
                    .where(RewardAllocation.quest_id == quest.id)
                )
            ).scalar_one()
        )
        if existing_winners > 0:
            log.info("seed_activity_exists")
            return

    # Create graded attempts for the first three students with distinct scores.
    scores = [9000, 8000, 7000]
    durations = [120, 90, 60]

    for student, score_bp, duration in zip(students[:3], scores, durations, strict=False):
        async with session_scope() as session:
            exam = (
                await session.execute(select(Exam).where(Exam.title == "Ujian Simulasi Dasar"))
            ).scalar_one()
            from app.models.exam import Question

            questions = list(
                (
                    await session.execute(
                        select(Question)
                        .where(Question.exam_id == exam.id)
                        .order_by(Question.position)
                    )
                )
                .scalars()
                .all()
            )
            if not questions:
                return
            from datetime import UTC, datetime, timedelta

            now = datetime.now(UTC)
            per_q = int(score_bp / len(questions))
            attempt = ExamAttempt(
                exam_id=exam.id,
                user_id=student.id,
                attempt_number=1,
                status="graded",
                score_bp=score_bp,
                passed=score_bp >= exam.passing_score_bp,
                started_at=now - timedelta(seconds=duration + 30),
                submitted_at=now,
                graded_at=now,
                duration_seconds=duration,
            )
            session.add(attempt)
            await session.flush()
            for q in questions:
                session.add(
                    StudentAnswer(
                        attempt_id=attempt.id,
                        question_id=q.id,
                        answer_text="Jawaban simulasi siswa.",
                        score_bp=min(per_q, q.max_score_bp),
                        max_score_bp=q.max_score_bp,
                        feedback="Jawaban cukup baik (simulasi).",
                        similarity_bp=int(per_q * 10000 / max(1, q.max_score_bp)),
                        graded_at=now,
                    )
                )
            await session.flush()

        from app.services.quest_service import QuestService

        async with session_scope() as session:
            quest = (
                await session.execute(select(Quest).where(Quest.title == "Quest Simulasi Cepat"))
            ).scalar_one()
            await QuestService(session).record_attempt(
                quest.id, student, exam_attempt_id=attempt.id
            )
            log.info("seed_attempt", student=str(student.id), score=score_bp)

    # Finalize the quest -> rewards, badges, notifications.
    async with session_scope() as session:
        quest = (
            await session.execute(select(Quest).where(Quest.title == "Quest Simulasi Cepat"))
        ).scalar_one()
        owner = (
            await session.execute(select(User).where(User.email == "teacher@qloot.example"))
        ).scalar_one()
        svc = QuestService(session)
        _, winners = await svc.finalize(quest.id, owner)
        rules = {r.rank: r for r in await svc.list_rules(quest.id)}

        from app.services.reward_engine import RewardEngine
        from app.services.social_service import BadgeService, NotificationService

        engine = RewardEngine(session)
        badges = BadgeService(session)
        notifier = NotificationService(session)
        for w in winners:
            rule = rules.get(w.rank)
            amount = rule.reward_amount if rule else 0
            user_row = await session.get(User, w.user_id)
            if user_row and amount > 0:
                await engine.allocate_quest_reward(
                    quest=quest, user=user_row, rank=w.rank, amount=amount, score_bp=w.score_bp
                )
                await notifier.notify(
                    user_id=user_row.id,
                    kind="reward",
                    title=f"You earned {amount} OPC!",
                    body=f"Quest '{quest.title}' — rank {w.rank}",
                    data={"quest_id": str(quest.id), "rank": w.rank},
                )
                await badges.award(user=user_row, code="first_reward")
                if w.rank <= 3:
                    await badges.award(user=user_row, code="top_3", meta={"rank": w.rank})
        log.info("seed_quest_finalized", winners=len(winners))

    # Simulate some task completions (idempotent) for the first two students.
    await _simulate_tasks(students)


async def _simulate_tasks(students: list[User]) -> None:
    """Complete the seeded tasks for a couple of students (idempotent)."""
    from sqlalchemy import select as _select

    from app.models.quest import Task, TaskCompletion
    from app.services.keys import task_reward_key
    from app.services.reward_engine import RewardEngine

    async with session_scope() as session:
        tasks = list((await session.execute(_select(Task))).scalars().all())
        if not tasks:
            return
        for student in students[:2]:
            for task in tasks:
                exists = (
                    await session.execute(
                        _select(TaskCompletion).where(
                            TaskCompletion.task_id == task.id,
                            TaskCompletion.user_id == student.id,
                        )
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    continue
                rkey = task_reward_key(task.id, student.id)
                session.add(TaskCompletion(task_id=task.id, user_id=student.id, reward_key=rkey))
                if task.reward_amount > 0:
                    await RewardEngine(session).allocate_task_reward(
                        user=student, task_id=task.id, amount=task.reward_amount, rkey=rkey
                    )
                log.info("seed_task_completed", student=str(student.id), task=str(task.id))


if __name__ == "__main__":
    asyncio.run(main())
