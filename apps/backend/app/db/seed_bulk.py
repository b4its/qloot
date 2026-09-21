"""Bulk seeder: pad the catalog to ~200 rows per table.

This complements the curated simulation in ``app.db.seed`` with a large,
deterministic volume of data so the UI, rankings and analytics are non-trivial:

  - exactly 5 teachers and 50 students spread across classes
  - ~200 rows in each "content" table (courses, lessons, materials, exams,
    questions, rooms, quests, tasks, badges, notifications, career tables,
    wallet ledger entries, ...)

Everything is idempotent: re-running only inserts what is missing, so it is
safe to run repeatedly against a live database. IDs are derived from stable
seeds (uuid5) so rows keep the same identity across runs.

Run with: ``python -m app.db.seed_bulk`` (or via ``app.db.seed``).
"""

from __future__ import annotations

import asyncio
import io
import random
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

log = get_logger("seed_bulk")

TARGET = 200  # rows per table

# Stable namespace so regenerating produces the same UUIDs.
NS = uuid.UUID("6f3d1c1a-0000-4000-8000-000000000001")


def det_uuid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(parts))


# --- names -----------------------------------------------------------------
_FIRST = [
    "Adi",
    "Budi",
    "Citra",
    "Dewi",
    "Eka",
    "Fajar",
    "Gita",
    "Hadi",
    "Indah",
    "Joko",
    "Kartika",
    "Lina",
    "Made",
    "Nadia",
    "Oki",
    "Putri",
    "Rangga",
    "Sinta",
    "Tono",
    "Umi",
    "Vina",
    "Wahyu",
    "Yoga",
    "Zahra",
    "Alya",
    "Bagas",
    "Cahya",
    "Dian",
    "Eko",
    "Fitri",
    "Galih",
    "Hana",
    "Iwan",
    "Jihan",
    "Krisna",
    "Lala",
    "Maya",
    "Nanda",
    "Omar",
    "Priska",
    "Rizki",
    "Sari",
    "Tari",
    "Ujang",
    "Wulan",
    "Yudi",
    "Zaki",
    "Ayu",
    "Bima",
    "Cindy",
]
_LAST = [
    "Santoso",
    "Wijaya",
    "Pratama",
    "Nugroho",
    "Maharani",
    "Aditya",
    "Nurhaliza",
    "Anjani",
    "Kusuma",
    "Hartono",
    "Setiawan",
    "Halim",
    "Permata",
    "Lestari",
    "Firmansyah",
]

CLASSES = [
    ("1A", "IPA"),
    ("1B", "IPA"),
    ("2A", "IPA"),
    ("2D", "IPS"),
    ("3A", "IPA"),
    ("3B", "IPS"),
]
SUBJECTS = [
    "Matematika",
    "Fisika",
    "Kimia",
    "Biologi",
    "B. Indonesia",
    "B. Inggris",
    "Sejarah",
    "Ekonomi",
    "Sosiologi",
    "Geografi",
]

# Real, text-rich PDFs from the internet (open course notes). If the network is
# unavailable the seeder falls back to a locally generated PDF so it always
# succeeds offline.
PDF_SOURCES = [
    "https://web.stanford.edu/class/cs224n/readings/cs224n-2019-notes01-wordvecs1.pdf",
    "https://web.stanford.edu/class/cs224n/readings/cs224n-2019-notes02-wordvecs2.pdf",
    "https://web.stanford.edu/class/cs224n/readings/cs224n-2019-notes03-neuralnets.pdf",
    "https://web.stanford.edu/class/cs224n/readings/cs224n-2019-notes04-dependencyparsing.pdf",
    "https://web.stanford.edu/class/cs224n/readings/cs224n-2019-notes05-language-models.pdf",
]


def _cache_pdf(url: str) -> tuple[bytes, str] | None:
    """Download a PDF and return (bytes, extracted_text), or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "QLoot-Seeder/1.0"})
        data = urllib.request.urlopen(req, timeout=25).read()
        if not data.startswith(b"%PDF"):
            return None
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return data, text[:500_000]
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf_fetch_failed", url=url, error=str(exc))
        return None


def _fallback_pdf(text: str) -> bytes:
    """Locally generated, valid PDF used when the network is unavailable."""
    stream = b"BT /F1 11 Tf 72 760 Td 14 TL (" + text.encode("latin-1", "ignore") + b") Tj ET"
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


async def _get_or_create_user(
    session: AsyncSession,
    email: str,
    full_name: str,
    role_name: str,
    class_code: str | None = None,
    class_type: str | None = None,
):
    from app.core.config import settings
    from app.core.security import hash_password
    from app.models.identity import Role, User, UserRole
    from app.services.auth_service import _compute_chain_user_ref  # type: ignore

    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        return existing

    role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one()
    uid = det_uuid("user", email)
    pw = {"admin": "AdminPass123!", "teacher": "TeacherPass123!", "student": "StudentPass123!"}[
        role_name
    ]
    user = User(
        id=uid,
        email=email,
        full_name=full_name,
        password_hash=hash_password(pw),
        chain_user_ref=_compute_chain_user_ref(settings.session_secret, uid),
        class_code=class_code,
        class_type=class_type,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=uid, role_id=role.id))
    # One custodial wallet per user.
    from app.models.wallet import WalletAccount

    session.add(WalletAccount(user_id=uid, token_id=0))
    await session.flush()
    return user


async def seed_accounts(session: AsyncSession):
    """Ensure exactly 5 teachers and 50 students in total.

    The curated demo accounts (teacher@, teacher2@, student1..5@) already exist;
    this tops the platform up to 5 teachers and 50 students spread across
    classes, using deterministic emails/ids so it stays idempotent.
    """
    from app.models.identity import Role, User, UserRole

    # Existing teachers/students (any origin).
    teacher_role_id = (
        await session.execute(select(Role.id).where(Role.name == "teacher"))
    ).scalar_one()
    teacher_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(UserRole.user_id))).where(
                    UserRole.role_id == teacher_role_id
                )
            )
        ).scalar_one()
    )
    student_total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(User)
                .where(User.email.like("%student%@qloot.example"))
            )
        ).scalar_one()
    )

    teachers = []
    i = 1
    while teacher_count + len(teachers) < 5:
        # Skip the curated "teacher2" slot name by using teacherN@ numbering.
        email = f"teacher{i + 2}@qloot.example"
        t = await _get_or_create_user(session, email, f"{_FIRST[i]} {_LAST[i]} (Guru)", "teacher")
        teachers.append(t)
        i += 1

    students = []
    n = student_total
    i = 1
    while n < 50:
        cc, ct = CLASSES[(n) % len(CLASSES)]
        email = f"student{n + 1:02d}@qloot.example"
        s = await _get_or_create_user(
            session,
            email,
            f"{_FIRST[(n + 1) % len(_FIRST)]} {_LAST[(n + 1) % len(_LAST)]}",
            "student",
            class_code=cc,
            class_type=ct,
        )
        students.append(s)
        n += 1
        i += 1

    # Always return the full roster (used by later steps for memberships).
    all_teachers = list(
        (await session.execute(select(User).where(User.email.like("teacher%@qloot.example"))))
        .scalars()
        .all()
    )
    all_students = list(
        (await session.execute(select(User).where(User.email.like("student%@qloot.example"))))
        .scalars()
        .all()
    )
    log.info("bulk_accounts_ready", teachers=len(all_teachers), students=len(all_students))
    return all_teachers, all_students


async def _count(session: AsyncSession, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def seed_courses_and_lessons(session: AsyncSession, teachers, students) -> None:
    from app.models.learning import Course, CourseMember, Lesson

    rng = random.Random(42)
    existing = {c[0] for c in (await session.execute(select(Course.title))).all()}
    made = 0
    for i in range(1, TARGET + 1):
        cc, ct = CLASSES[i % len(CLASSES)]
        subject = SUBJECTS[i % len(SUBJECTS)]
        title = f"{subject} — Kelas {cc} #{i:03d}"
        if title in existing:
            continue
        owner = teachers[i % len(teachers)]
        course = Course(
            id=det_uuid("course", str(i)),
            title=title,
            slug=f"{subject.lower().replace(' ', '-').replace('.', '')}-{cc.lower()}-{i:03d}",
            description=f"Materi {subject} untuk kelas {cc} ({ct}). Batch {i}.",
            owner_id=owner.id,
            is_published=True,
            class_code=cc,
            class_type=ct,
            subject=subject,
            on_chain_id=i,
        )
        session.add(course)
        session.add(CourseMember(course_id=course.id, user_id=owner.id, role="teacher"))
        # A few students per class join the course.
        for s in students:
            if s.class_code == cc and rng.random() < 0.6:
                session.add(CourseMember(course_id=course.id, user_id=s.id, role="student"))
        made += 1
        if made % 50 == 0:
            await session.flush()
            log.info("bulk_courses", progress=made)
    await session.flush()

    # Lessons: ~3 per course -> well over 200.
    existing_lessons = int(
        (await session.execute(select(func.count()).select_from(Lesson))).scalar_one()
    )
    if existing_lessons >= TARGET:
        return
    courses = list((await session.execute(select(Course).order_by(Course.created_at))).scalars())
    n = existing_lessons
    for course in courses:
        for pos in range(3):
            if n >= TARGET * 3:
                break
            session.add(
                Lesson(
                    id=det_uuid("lesson", str(course.id), str(pos)),
                    course_id=course.id,
                    title=f"Pertemuan {pos + 1}: {course.subject or 'Umum'}",
                    content_md=(
                        f"# {course.title}\n\nMateri pertemuan {pos + 1} untuk {course.subject}."
                    ),
                    position=pos,
                    is_published=True,
                )
            )
            n += 1
    await session.flush()
    log.info("bulk_lessons_ready", count=n)


async def seed_materials(session: AsyncSession, teachers) -> None:
    """~200 materials whose extracted text comes from real internet PDFs."""
    from app.models.learning import LearningMaterial

    if await _count(session, LearningMaterial) >= TARGET:
        return

    # Pull the real PDFs once, then reuse their bytes/text across materials.
    sources: list[tuple[bytes, str]] = []
    for url in PDF_SOURCES:
        got = _cache_pdf(url)
        if got:
            sources.append(got)
            log.info("pdf_cached", url=url, size=len(got[0]))
    if not sources:
        log.warning("pdf_sources_unavailable_using_fallback")
        text = (
            "Materi pembelajaran QLoot mencakup matematika, sains, bahasa dan sosial. "
            "Setiap materi disusun bertahap dari konsep dasar hingga penerapan. "
            "Fotosintesis mengubah cahaya matahari menjadi energi kimia di kloroplas."
        )
        sources = [(_fallback_pdf(text), text)]

    from app.services.storage import build_key, sha256_hex, storage

    existing = int(
        (await session.execute(select(func.count()).select_from(LearningMaterial))).scalar_one()
    )
    for i in range(existing + 1, TARGET + 1):
        owner = teachers[i % len(teachers)]
        data, text = sources[i % len(sources)]
        filename = f"materi-online-{i:03d}.pdf"
        key = build_key(owner.id, filename)
        storage.put(key, data, "application/pdf")
        session.add(
            LearningMaterial(
                id=det_uuid("material", str(i)),
                owner_id=owner.id,
                filename=filename,
                content_type="application/pdf",
                size_bytes=len(data),
                checksum_sha256=sha256_hex(data + str(i).encode()),
                storage_key=key,
                extracted_text=text,
                status="ready",
            )
        )
    await session.flush()
    log.info("bulk_materials_ready")


async def seed_exams_and_questions(session: AsyncSession, teachers) -> None:
    from app.models.exam import Exam, Question

    if await _count(session, Exam) < TARGET:
        existing = {t for (t,) in (await session.execute(select(Exam.title))).all()}
        for i in range(1, TARGET + 1):
            title = f"Ujian Simulasi #{i:03d}"
            if title in existing:
                continue
            owner = teachers[i % len(teachers)]
            session.add(
                Exam(
                    id=det_uuid("exam", str(i)),
                    title=title,
                    owner_id=owner.id,
                    duration_minutes=30 + (i % 60),
                    status="published",
                    is_active=True,
                    passing_score_bp=6000,
                    instructions="Jawab ringkas dan jelas.",
                )
            )
        await session.flush()

    # Questions: ~3 per exam (600 total, >= 200).
    if await _count(session, Question) >= TARGET:
        return
    exams = list((await session.execute(select(Exam))).scalars())
    for exam in exams:
        for pos in range(3):
            session.add(
                Question(
                    id=det_uuid("question", str(exam.id), str(pos)),
                    exam_id=exam.id,
                    owner_id=exam.owner_id,
                    prompt=f"[{exam.title}] Jelaskan konsep utama bagian {pos + 1}.",
                    correct_answer=(
                        "Pembahasan konsep utama beserta contoh penerapannya pada materi terkait."
                    ),
                    position=pos,
                    source="ai",
                    review_status="approved",
                )
            )
    await session.flush()
    log.info("bulk_exams_questions_ready")


async def seed_rooms(session: AsyncSession, teachers, students) -> None:
    from app.models.room import Room, RoomMember

    if await _count(session, Room) < TARGET:
        existing = {c for (c,) in (await session.execute(select(Room.code))).all()}
        for i in range(1, TARGET + 1):
            code = f"RM{i:04d}"
            if code in existing:
                continue
            owner = teachers[i % len(teachers)]
            session.add(
                Room(
                    id=det_uuid("room", str(i)),
                    name=f"Ruang Belajar #{i:03d}",
                    code=code,
                    owner_id=owner.id,
                    status="open",
                    max_participants=100,
                    is_public=True,
                )
            )
        await session.flush()

    if await _count(session, RoomMember) >= TARGET:
        return
    rooms = list((await session.execute(select(Room))).scalars())
    # Existing (room, user) pairs so re-running never violates the unique key.
    existing_pairs = {
        (rm.room_id, rm.user_id) for rm in (await session.execute(select(RoomMember))).scalars()
    }
    rng = random.Random(7)
    for room in rooms:
        if (room.id, room.owner_id) not in existing_pairs:
            session.add(
                RoomMember(room_id=room.id, user_id=room.owner_id, role="teacher", is_present=True)
            )
            existing_pairs.add((room.id, room.owner_id))
        for s in rng.sample(students, k=3):
            pair = (room.id, s.id)
            if pair in existing_pairs:
                continue
            session.add(RoomMember(room_id=room.id, user_id=s.id, role="student", is_present=True))
            existing_pairs.add(pair)
    await session.flush()
    log.info("bulk_rooms_ready")


async def seed_quests_and_tasks(session: AsyncSession, teachers) -> None:
    from app.models.quest import Quest, QuestRule, Task

    if await _count(session, Quest) < TARGET:
        existing = {t for (t,) in (await session.execute(select(Quest.title))).all()}
        for i in range(1, TARGET + 1):
            title = f"Quest Harian #{i:03d}"
            if title in existing:
                continue
            q = Quest(
                id=det_uuid("quest", str(i)),
                title=title,
                description="Kumpulkan poin sebanyak mungkin untuk naik peringkat.",
                owner_id=teachers[i % len(teachers)].id,
                status="open" if i % 3 else "draft",
                top_n_winners=3,
            )
            session.add(q)
            for rank, amt in enumerate([100, 60, 40], start=1):
                session.add(QuestRule(quest_id=q.id, rank=rank, reward_amount=amt))
        await session.flush()

    if await _count(session, Task) >= TARGET:
        return
    kinds = ["daily", "learning", "exam"]
    for i in range(1, TARGET + 1):
        session.add(
            Task(
                id=det_uuid("task", str(i)),
                title=f"Tugas {kinds[i % 3].title()} #{i:03d}",
                description="Selesaikan aktivitas untuk mendapatkan OPC.",
                owner_id=teachers[i % len(teachers)].id,
                kind=kinds[i % 3],
                reward_amount=5 + (i % 20),
                is_active=True,
            )
        )
    await session.flush()
    log.info("bulk_quests_tasks_ready")


async def seed_career(session: AsyncSession, students) -> None:
    from app.models.career import AcademicGrade, Consultation, PersonalityResult, ResourceItem

    terms = ["2024/2025-ganjil", "2024/2025-genap", "2025/2026-ganjil", "2025/2026-genap"]

    # Grades: 4 subjects x 4 terms x 50 students = 800 rows.
    if await _count(session, AcademicGrade) < TARGET:
        rng = random.Random(11)
        # Skip (user, subject, term) combos the curated simulation already made.
        existing_keys = {
            (g.user_id, g.subject, g.term)
            for g in (await session.execute(select(AcademicGrade))).scalars()
        }
        for s in students:
            for subject in ["Fisika", "Matematika", "Kimia", "B. Inggris"]:
                for term in terms:
                    key = (s.id, subject, term)
                    if key in existing_keys:
                        continue
                    existing_keys.add(key)
                    session.add(
                        AcademicGrade(
                            id=det_uuid("grade", str(s.id), subject, term),
                            user_id=s.id,
                            subject=subject,
                            grade=rng.randint(55, 98),
                            term=term,
                        )
                    )
        await session.flush()

    # Personality: one per student (50) plus padding to 200 via stored answers.
    if await _count(session, PersonalityResult) < TARGET:
        rng = random.Random(13)
        i = 0
        while i < TARGET:
            s = students[i % len(students)]
            i += 1
            vals = [rng.randint(1, 5) for _ in range(5)]
            session.add(
                PersonalityResult(
                    id=det_uuid("personality", str(i)),
                    user_id=s.id,
                    openness=vals[0] * 20,
                    conscientiousness=vals[1] * 20,
                    extraversion=vals[2] * 20,
                    agreeableness=vals[3] * 20,
                    neuroticism=vals[4] * 20,
                    summary="Profil kepribadian (simulasi).",
                    answers=vals,
                )
            )
        await session.flush()

    if await _count(session, Consultation) < TARGET:
        rng = random.Random(17)
        counselors = ["Bu Ratna Wijaya", "Pak Aditya Nugraha"]
        for i in range(1, TARGET + 1):
            s = students[i % len(students)]
            session.add(
                Consultation(
                    id=det_uuid("consult", str(i)),
                    user_id=s.id,
                    counselor=counselors[i % 2],
                    topic="Konsultasi pemilihan jurusan",
                    scheduled_at=datetime.now(UTC) + timedelta(days=3 + i % 10),
                    status="pending" if i % 4 else "cancelled",
                    notes="Sesi simulasi.",
                )
            )
        await session.flush()

    # Resources: keep the curated catalog, pad to 200 with generated entries.
    if await _count(session, ResourceItem) < TARGET:
        existing = {c for (c,) in (await session.execute(select(ResourceItem.code))).all()}
        cats = ["course", "extracurricular", "material"]
        for i in range(1, TARGET + 1):
            code = f"res-auto-{i:03d}"
            if code in existing:
                continue
            cat = cats[i % 3]
            session.add(
                ResourceItem(
                    id=det_uuid("resource", str(i)),
                    code=code,
                    category=cat,
                    title=f"{cat.title()} Rekomendasi #{i:03d}",
                    description="Rekomendasi belajar (simulasi).",
                    provider="QLoot",
                    is_free=bool(i % 2),
                    tags=[SUBJECTS[i % len(SUBJECTS)]],
                )
            )
        await session.flush()
    log.info("bulk_career_ready")


async def seed_notifications(session: AsyncSession, students, teachers) -> None:
    from app.models.social import Notification

    if await _count(session, Notification) >= TARGET:
        return
    everyone = students + teachers
    rng = random.Random(23)
    kinds = ["system", "reward", "quest", "badge", "room"]
    for i in range(1, TARGET + 1):
        u = everyone[i % len(everyone)]
        session.add(
            Notification(
                id=det_uuid("notif", str(i)),
                user_id=u.id,
                kind=kinds[i % len(kinds)],
                title=f"Pemberitahuan #{i:03d}",
                body="Kabar terbaru dari QLoot (simulasi).",
                data={"index": i},
                read_at=datetime.now(UTC) if rng.random() < 0.4 else None,
            )
        )
    await session.flush()
    log.info("bulk_notifications_ready")


async def seed_ledger(session: AsyncSession, students) -> None:
    from app.models.wallet import WalletAccount, WalletLedgerEntry

    if await _count(session, WalletLedgerEntry) >= TARGET:
        return
    accounts = {a.user_id: a for a in (await session.execute(select(WalletAccount))).scalars()}
    rng = random.Random(29)
    made = 0
    for s in students:
        acc = accounts.get(s.id)
        if acc is None:
            continue
        balance = 0
        for j in range(4):
            amount = rng.randint(5, 50)
            balance += amount
            session.add(
                WalletLedgerEntry(
                    id=det_uuid("ledger", str(s.id), str(j)),
                    account_id=acc.id,
                    token_id=0,
                    entry_type="credit",
                    amount=amount,
                    balance_after=balance,
                    reference_type="reward",
                    reference_id=f"seed-{s.id}-{j}",
                    reward_key=None,
                    description="Reward simulasi (seed).",
                )
            )
            made += 1
        acc.cached_balance = balance
    await session.flush()
    log.info("bulk_ledger_ready", entries=made)


async def seed_badges(session: AsyncSession) -> None:
    """Pad the badge catalog to ~200 achievements.

    The curated 7 gameplay badges stay; we add themed milestone badges so the
    catalog (and the on-chain id space) is rich without breaking existing ones.
    """
    from app.models.social import Badge

    if await _count(session, Badge) >= TARGET:
        return
    existing = {c for (c,) in (await session.execute(select(Badge.code))).all()}
    themes = ["XP", "Streak", "Quiz", "Course", "Quest", "Room", "Badge", "Leaderboard"]
    icons = ["🥇", "🥈", "🥉", "🎖️", "🏆", "⭐", "🌟", "💠", "🔥", "🧭", "🚀", "📘"]
    made = 0
    for i in range(1, TARGET + 1):
        code = f"achv-{i:03d}"
        if code in existing:
            continue
        theme = themes[i % len(themes)]
        session.add(
            Badge(
                code=code,
                name=f"{theme} Milestone {i:03d}",
                description=f"Raih tonggak {theme} tingkat {i}.",
                icon=icons[i % len(icons)],
                points=5 * ((i % 20) + 1),
            )
        )
        made += 1
    await session.flush()
    # Assign sequential on-chain ids to the newly added badges as well.
    from app.services.social_service import BadgeService

    await BadgeService(session)._assign_on_chain_ids()
    log.info("bulk_badges_ready", added=made)


async def seed_community(session: AsyncSession, students) -> None:
    """Seed the community feed with ~200 posts + comments + likes."""
    from app.models.community import CommunityComment, CommunityLike, CommunityPost
    from app.services.community_service import TOPICS

    if await _count(session, CommunityPost) >= TARGET:
        return
    rng = random.Random(31)
    bodies = [
        "Tips menyusun portofolio: mulai dari masalah, bukan dari visual.",
        "Rekaman sesi minggu ini sudah tersedia di kelas. Silakan disimak!",
        "Kumpulan dataset publik untuk latihan visualisasi — cek tautan di kelas.",
        "Bagaimana cara efektif belajar untuk ujian? Ini strategi saya…",
        "Baru selesai quest pertama, seru! Ada tips menaikkan skor?",
        "Materi Fisika pekan ini menantang. Mari diskusi di kolom komentar.",
        "Sertifikat digital sekarang bisa diverifikasi lewat tautan unik, keren!",
        "Berbagi ringkasan bab 3 — semoga membantu teman-teman sekelas.",
        "Kuis AI-nya lumayan akurat untuk latihan esai. Rekomendasi!",
        "Ada yang ingin belajar bareng di ruang simulasi sore ini?",
    ]
    made = 0
    comment_made = 0
    like_made = 0
    posts: list[CommunityPost] = []
    for i in range(1, TARGET + 1):
        author = students[i % len(students)]
        topic = TOPICS[i % len(TOPICS)]
        post = CommunityPost(
            id=det_uuid("cpost", str(i)),
            author_id=author.id,
            topic=topic,
            body=f"{bodies[i % len(bodies)]} (#{i:03d})",
            like_count=0,
            comment_count=0,
            created_at=datetime.now(UTC) - timedelta(hours=i),
        )
        session.add(post)
        posts.append(post)
        made += 1

    # Flush posts FIRST so comment/like rows (which have a FK but no ORM
    # relationship) never reference un-flushed posts.
    await session.flush()

    for i, post in enumerate(posts, start=1):
        # 0-3 comments per post.
        n_comments = i % 4
        for c in range(n_comments):
            commenter = students[(i + c) % len(students)]
            session.add(
                CommunityComment(
                    id=det_uuid("ccomment", str(i), str(c)),
                    post_id=post.id,
                    author_id=commenter.id,
                    body="Setuju! Terima kasih berbaginya.",
                    created_at=datetime.now(UTC) - timedelta(hours=i, minutes=-c),
                )
            )
            comment_made += 1
        post.comment_count = n_comments
        # A few likes spread across students (deterministic ids).
        likers = rng.sample(students, k=min(len(students), i % 6))
        for li, s in enumerate(likers):
            session.add(
                CommunityLike(
                    id=det_uuid("clike", str(i), str(li)),
                    post_id=post.id,
                    user_id=s.id,
                )
            )
            like_made += 1
        post.like_count = len(likers)
    await session.flush()
    log.info("bulk_community_ready", posts=made, comments=comment_made, likes=like_made)


async def main() -> None:
    from app.db.session import session_scope
    from app.services.social_service import BadgeService

    log.info("seed_bulk_start")
    async with session_scope() as session:
        await BadgeService(session).ensure_catalog()
        teachers, students = await seed_accounts(session)
        await seed_badges(session)
        await seed_courses_and_lessons(session, teachers, students)
        await seed_materials(session, teachers)
        await seed_exams_and_questions(session, teachers)
        await seed_rooms(session, teachers, students)
        await seed_quests_and_tasks(session, teachers)
        await seed_career(session, students)
        await seed_notifications(session, students, teachers)
        await seed_community(session, students)
        await seed_ledger(session, students)

        # Part 2: fill the remaining tables (attempts, grading, certificates,
        # quest outcomes, leaderboards, audit/ops and blockchain tables).
        from app.db import seed_bulk_extra as extra

        await extra.seed_attempts_and_grading(session, students)
        await extra.seed_progress_and_certificates(session, students)
        await extra.seed_quest_outcomes(session, students)
        await extra.seed_progress_boards(session, students, teachers)
        await extra.seed_ops_tables(session, students, teachers)
        await extra.seed_misc(session, students, teachers)
    log.info("seed_bulk_done")


if __name__ == "__main__":
    asyncio.run(main())
