"""Realistic support-data seeder for the QLoot demo.

This module seeds the platform's *supporting* data — accounts, the badge
catalogue, study rooms, tasks, the community feed, career/BK data, wallet
ledger, notifications and ops/blockchain rows — with believable content instead
of ``… #001`` filler.

It deliberately does **not** create the curriculum catalogue or the learning
history: those live in :mod:`app.db.seed_timeline`, which replays the real flow
(class → lessons → exams → grading → rewards → certificates) across a real
calendar at 100–200 learning records per month. ``main`` here covers everything
else, then delegates the timeline to make the demo coherent.

Everything is deterministic (uuid5 ids from stable seeds) and idempotent
(row-count guards + stable ids), so it is safe to run repeatedly against a live
database.

Run with: ``python -m app.db.seed_bulk`` (or via ``app.db.seed``).
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

log = get_logger("seed_bulk")

# Kept for backwards-compatibility with callers/tests that import it. The
# timeline seeder decides its own volume; this is only a loose upper bound used
# by a couple of "fill to N" helpers below.
TARGET = 200

# Stable namespace so regenerating produces the same UUIDs.
NS = uuid.UUID("6f3d1c1a-0000-4000-8000-000000000001")


def det_uuid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(NS, "|".join(parts))


# --- realistic people ------------------------------------------------------
# A wider, more genuine Indonesian name pool so the 50-student roster reads like
# a real cohort rather than "Budi Santoso" repeated.
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
    "Ramadhan",
    "Saputra",
    "Anggraini",
    "Maulana",
    "Handayani",
]

# Class roster matches the curriculum in :mod:`app.db.content`.
CLASSES = [
    ("10A", "IPA"),
    ("10B", "IPS"),
    ("11A", "IPA"),
    ("11B", "IPS"),
    ("12A", "IPA"),
    ("12B", "IPS"),
]


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
    from app.services.auth_service import _compute_chain_user_ref

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
    # One custodial wallet per user; personal wallet defaults to the platform one.
    from app.models.wallet import WalletAccount
    from app.services.wallet_service import default_wallet_address

    session.add(
        WalletAccount(user_id=uid, token_id=0, withdrawal_address=default_wallet_address() or None)
    )
    await session.flush()
    return user


async def seed_accounts(session: AsyncSession):
    """Ensure exactly 5 teachers and 50 students in total.

    The curated demo accounts (teacher@, teacher2@, student1..5@) already exist;
    this tops the platform up to 5 teachers and 50 students spread across
    classes, using deterministic emails/ids so it stays idempotent.
    """
    from app.models.identity import Role, User, UserRole

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

    teachers: list[User] = []
    i = 1
    while teacher_count + len(teachers) < 5:
        email = f"teacher{i + 2}@qloot.example"
        t = await _get_or_create_user(session, email, f"{_FIRST[i]} {_LAST[i]}", "teacher")
        teachers.append(t)
        i += 1

    students = []
    n = student_total
    while n < 50:
        cc, ct = CLASSES[n % len(CLASSES)]
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


async def _all_students(session: AsyncSession) -> list:
    from app.models.identity import User

    return list(
        (await session.execute(select(User).where(User.email.like("student%@qloot.example"))))
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Rooms (real study rooms, not "Ruang Belajar #042")
# ---------------------------------------------------------------------------
ROOM_BANK: list[tuple[str, str]] = [
    ("Ruang Belajar Matematika Malam", "Diskusi soal dan latihan bersama tiap Selasa & Kamis."),
    ("Klub Debat Bahasa Inggris", "Latihan speaking & debat mingguan dalam bahasa Inggris."),
    ("Sesi Tanya Jawab UTBK", "Bedah soal UTBK per subtes bersama kakak alumni."),
    ("Lab Fisika Virtual", "Praktikum kinematika & listrik yang bisa diikuti dari rumah."),
    ("Ruang Bimbingan Karier", "Sesi sharing jurusan kuliah dan dunia kerja."),
    ("Kelas Literasi & Menulis", "Belajar menulis esai, cerpen, dan karya ilmiah remaja."),
    ("Belajar Bareng Biologi", "Rangkuman materi sel, genetika, dan sistem organ."),
    ("Diskusi Ekonomi & Bisnis", "Simulasi pasar, kewirausahaan, dan literasi keuangan."),
]


async def seed_rooms(session: AsyncSession, teachers, students) -> None:
    from app.models.room import Room, RoomMember

    existing = {c for (c,) in (await session.execute(select(Room.code))).all()}
    rng = random.Random(7)
    for i, (name, _desc) in enumerate(ROOM_BANK):
        code = f"RM{i + 1:04d}"
        if code in existing:
            continue
        owner = teachers[i % len(teachers)]
        room_id = det_uuid("room", name)
        session.add(
            Room(
                id=room_id,
                name=name,
                code=code,
                owner_id=owner.id,
                status="open",
                max_participants=60,
                is_public=True,
            )
        )
        session.add(RoomMember(room_id=room_id, user_id=owner.id, role="teacher", is_present=True))
        for s in rng.sample(students, k=min(len(students), 12)):
            session.add(RoomMember(room_id=room_id, user_id=s.id, role="student", is_present=True))
    await session.flush()
    log.info("bulk_rooms_ready", rooms=len(ROOM_BANK))


# ---------------------------------------------------------------------------
# Tasks (real tasks, mirroring the app's kinds)
# ---------------------------------------------------------------------------
async def seed_tasks(session: AsyncSession, teachers, students) -> None:
    from app.db.content import TASK_BANK
    from app.models.quest import Task

    existing = {t for (t,) in (await session.execute(select(Task.title))).all()}
    for i, (title, desc, kind, reward) in enumerate(TASK_BANK):
        if title in existing:
            continue
        session.add(
            Task(
                id=det_uuid("task", title),
                title=title,
                description=desc,
                owner_id=teachers[i % len(teachers)].id,
                kind=kind,
                reward_amount=reward,
                is_active=True,
            )
        )
    await session.flush()
    log.info("bulk_tasks_ready", tasks=len(TASK_BANK))


# ---------------------------------------------------------------------------
# Quests (real, themed competitions) + rules
# ---------------------------------------------------------------------------
QUEST_BANK: list[tuple[str, str]] = [
    ("Kuis Cepat Matematika", "Peringkat 1 menang — soal eksponen & barisan."),
    ("Tantangan Fisika Kinematika", "Selesaikan soal gerak tercepat dan tepat."),
    ("Lomba Kuis Biologi Sel", "Kompetisi singkat materi sel & genetika."),
    ("Olimpiade Ekonomi Mini", "Uji pemahaman pasar dan kebijakan ekonomi."),
    ("Duel Sejarah Kemerdekaan", "Jawab soal sejarah paling banyak dengan benar."),
    ("Kuis Bahasa Inggris Kilat", "Descriptive & narrative dalam waktu singkat."),
]


async def seed_quests(session: AsyncSession, teachers, exams) -> list:
    from app.models.quest import Quest, QuestRule

    existing = {t for (t,) in (await session.execute(select(Quest.title))).all()}
    quests = []
    for i, (title, desc) in enumerate(QUEST_BANK):
        if title in existing:
            continue
        exam = exams[i % len(exams)] if exams else None
        q = Quest(
            id=det_uuid("quest", title),
            title=title,
            description=desc,
            owner_id=teachers[i % len(teachers)].id,
            exam_id=exam.id if exam else None,
            status="open",
            kind="exam",
            top_n_winners=3,
            opens_at=datetime(2025, 1 + (i % 6), 1, tzinfo=UTC),
        )
        session.add(q)
        for rank, amt in enumerate([100, 60, 40], start=1):
            session.add(QuestRule(quest_id=q.id, rank=rank, reward_amount=amt))
        quests.append(q)
    await session.flush()
    log.info("bulk_quests_ready", quests=len(quests))
    return list((await session.execute(select(Quest))).scalars().all())


# ---------------------------------------------------------------------------
# Community feed (real posts/comments/likes, dated across 2025+)
# ---------------------------------------------------------------------------
async def seed_community(session: AsyncSession, students) -> None:
    from app.db.content import COMMUNITY_COMMENTS, COMMUNITY_POSTS
    from app.models.community import CommunityComment, CommunityLike, CommunityPost

    if await _count(session, CommunityPost) >= TARGET:
        return
    rng = random.Random(31)
    # Spread posts across a realistic window (weekly cadence since Jan 2025).
    base = datetime(2025, 1, 6, 10, 0, tzinfo=UTC)
    posts: list[CommunityPost] = []
    for i in range(TARGET):
        topic, body = COMMUNITY_POSTS[i % len(COMMUNITY_POSTS)]
        author = students[i % len(students)]
        created = base + timedelta(days=i * 3, hours=rng.randint(0, 8))
        post = CommunityPost(
            id=det_uuid("cpost", str(i)),
            author_id=author.id,
            topic=topic,
            body=body,
            like_count=0,
            comment_count=0,
            created_at=created,
        )
        session.add(post)
        posts.append(post)
    await session.flush()

    for i, post in enumerate(posts):
        n_comments = i % 3  # 0-2 comments, realistic for a small class feed
        for c in range(n_comments):
            commenter = students[(i + c + 1) % len(students)]
            session.add(
                CommunityComment(
                    id=det_uuid("ccomment", str(i), str(c)),
                    post_id=post.id,
                    author_id=commenter.id,
                    body=COMMUNITY_COMMENTS[(i + c) % len(COMMUNITY_COMMENTS)],
                    created_at=post.created_at + timedelta(hours=1 + c),
                )
            )
        post.comment_count = n_comments
        likers = rng.sample(students, k=min(len(students), i % 8))
        for li, s in enumerate(likers):
            session.add(
                CommunityLike(
                    id=det_uuid("clike", str(i), str(li)),
                    post_id=post.id,
                    user_id=s.id,
                    created_at=post.created_at + timedelta(minutes=30 * (li + 1)),
                )
            )
        post.like_count = len(likers)
    await session.flush()
    log.info("bulk_community_ready", posts=len(posts))


# ---------------------------------------------------------------------------
# Badges (earnable XP milestones — unchanged behaviour, real catalog)
# ---------------------------------------------------------------------------
async def seed_badges(session: AsyncSession) -> None:
    from app.models.social import Badge
    from app.services.social_service import XP_MILESTONES, _milestone_badge_row

    existing = {c for (c,) in (await session.execute(select(Badge.code))).all()}
    made = 0
    for _xp, code, name, desc, icon, points in XP_MILESTONES:
        if code in existing:
            continue
        session.add(Badge(**_milestone_badge_row(code, name, desc, icon, points)))
        made += 1
    await session.flush()
    log.info("bulk_badges_ready", added=made)


# ---------------------------------------------------------------------------
# Career: grades, personality, consultations, recommendations, resources
# ---------------------------------------------------------------------------
async def seed_career(session: AsyncSession, students) -> None:
    from app.db.content import CAREER_RESOURCES, CONSULTATION_TOPICS, COUNSELORS, MAJORS, TERMS
    from app.models.career import (
        AcademicGrade,
        CareerRecommendation,
        Consultation,
        PersonalityResult,
        ResourceItem,
    )
    from app.models.identity import Role, User, UserRole

    # --- Academic grades: realistic per-subject spread, multiple terms -------
    subject_pool = ["Matematika", "Fisika", "Kimia", "Biologi", "B. Indonesia", "B. Inggris"]
    existing_keys = {
        (g.user_id, g.subject, g.term)
        for g in (await session.execute(select(AcademicGrade))).scalars()
    }
    rng = random.Random(11)
    for si, s in enumerate(students):
        # A per-student "ability" so grades correlate across subjects/terms.
        ability = rng.randint(68, 92)
        subjects = subject_pool[:4] if (si % 2 == 0) else subject_pool[2:6]
        for subject in subjects:
            for term_idx, term in enumerate(TERMS):
                key = (s.id, subject, term)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                # Small per-subject offset + gentle term-on-term drift.
                grade = max(
                    55,
                    min(99, ability + rng.randint(-8, 8) + term_idx),
                )
                session.add(
                    AcademicGrade(
                        id=det_uuid("grade", str(s.id), subject, term),
                        user_id=s.id,
                        subject=subject,
                        grade=grade,
                        term=term,
                    )
                )
    await session.flush()

    # --- Personality: one per student, plausible OCEAN spread ---------------
    existing_personality = {
        p.user_id for p in (await session.execute(select(PersonalityResult))).scalars()
    }
    for _si, s in enumerate(students):
        if s.id in existing_personality:
            continue
        rng = random.Random(f"ocean:{s.id}")
        vals = [rng.randint(2, 5) for _ in range(5)]
        session.add(
            PersonalityResult(
                id=det_uuid("personality", str(s.id)),
                user_id=s.id,
                openness=vals[0] * 20,
                conscientiousness=vals[1] * 20,
                extraversion=vals[2] * 20,
                agreeableness=vals[3] * 20,
                neuroticism=vals[4] * 20,
                summary="Profil kepribadian Big Five (asesmen mandiri).",
                answers=vals * 6,
            )
        )
    await session.flush()

    # --- Consultations: real topics, every status represented ----------------
    counselor_user = (
        (
            await session.execute(
                select(User)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.name == "teacher")
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    existing_consult = {
        c.id for c in (await session.execute(select(Consultation))).scalars()
    }
    statuses = ["pending", "accepted", "completed", "cancelled"]
    # Fixed anchor so re-runs produce identical (idempotent) timestamps.
    consult_base = datetime(2025, 1, 8, 9, 0, tzinfo=UTC)
    for i in range(min(TARGET, len(students) * 4)):
        s = students[i % len(students)]
        topic = CONSULTATION_TOPICS[i % len(CONSULTATION_TOPICS)]
        status = statuses[i % len(statuses)]
        scheduled = consult_base + timedelta(days=i, hours=i % 8)
        consult_id = det_uuid("consult", str(i))
        if consult_id in existing_consult:
            continue
        existing_consult.add(consult_id)
        session.add(
            Consultation(
                id=consult_id,
                user_id=s.id,
                counselor=COUNSELORS[i % len(COUNSELORS)],
                counselor_user_id=counselor_user.id if counselor_user else None,
                topic=topic,
                scheduled_at=scheduled,
                status=status,
                completed_at=(scheduled + timedelta(hours=1) if status == "completed" else None),
                notes="Catatan sesi bimbingan konseling.",
            )
        )
    await session.flush()

    # --- Recommendations: tailored to the student's strongest subjects ------
    existing_rec = {
        (r.user_id, r.major, r.rank)
        for r in (await session.execute(select(CareerRecommendation))).scalars()
    }
    grades_by_user: dict[uuid.UUID, list[AcademicGrade]] = {}
    for g in (await session.execute(select(AcademicGrade))).scalars():
        grades_by_user.setdefault(g.user_id, []).append(g)
    for s in students:
        rows = grades_by_user.get(s.id, [])
        top = sorted(rows, key=lambda g: g.grade, reverse=True)[:3]
        top_subjects = [g.subject for g in top]
        # Rank majors by how many of the student's top subjects they match.
        ranked = sorted(
            MAJORS,
            key=lambda m: -len(set(m["rationale_best_for"]) & set(top_subjects)),
        )
        for rank, major in enumerate(ranked[:3], start=1):
            rec_key = (s.id, major["major"], rank)
            if rec_key in existing_rec:
                continue
            existing_rec.add(rec_key)
            match = len(set(major["rationale_best_for"]) & set(top_subjects))
            base = 70 + match * 8
            session.add(
                CareerRecommendation(
                    id=det_uuid("crec", str(s.id), str(major["major"]), str(rank)),
                    user_id=s.id,
                    major=str(major["major"]),
                    fit_score=min(98, base + 2),
                    academic_fit=min(98, base + 4),
                    personality_fit=min(98, base),
                    rationale=(
                        f"Cocok dengan kekuatan akademik pada "
                        f"{', '.join(top_subjects) or 'mapel inti'} "
                        f"dan profil kepribadian Anda."
                    ),
                    universities=list(major["universities"]),
                    admission_paths=list(major["admission_paths"]),
                    skills=list(major["skills"]),
                    careers=list(major["careers"]),
                    rank=rank,
                    status=["draft", "in_review", "approved"][rank % 3],
                    created_at=consult_base + timedelta(days=rank * 3),
                )
            )
    await session.flush()

    # --- Resources: the curated catalogue (idempotent by code) --------------
    existing_res = {c for (c,) in (await session.execute(select(ResourceItem.code))).all()}
    for spec in CAREER_RESOURCES:
        code = str(spec["code"])
        if code in existing_res:
            continue
        session.add(
            ResourceItem(
                id=det_uuid("resource", code),
                code=code,
                category=str(spec["category"]),
                title=str(spec["title"]),
                description=str(spec["description"]),
                provider=str(spec["provider"]),
                is_free=bool(spec["is_free"]),
                tags=list(spec["tags"]),
            )
        )
    await session.flush()
    log.info("bulk_career_ready")


# ---------------------------------------------------------------------------
# Notifications (real, kind-appropriate copy)
# ---------------------------------------------------------------------------
async def seed_notifications(session: AsyncSession, students, teachers) -> None:
    from app.models.social import Notification

    if await _count(session, Notification) >= TARGET:
        return
    everyone = students + teachers
    rng = random.Random(23)
    # (kind, title template, body template)
    templates = [
        ("reward", "Kamu mendapat {n} OPT", "Hadiah dari aktivitas belajar tersimpan di dompetmu."),
        ("quest", "Quest baru dibuka", "Ada kompetisi baru — ikut untuk naik peringkat!"),
        ("badge", "Badge baru terbuka", "Konsisten belajar membuka lencana baru untukmu."),
        ("room", "Undangan ruang belajar", "Gurumu mengundangmu ke sesi belajar daring."),
        ("system", "Jadwal ujian diperbarui", "Periksa jadwal ujian terbaru di dasbor."),
        ("notification", "Materi baru diunggah", "Guru menambahkan materi baru di kelasmu."),
    ]
    base = datetime(2025, 1, 2, 8, 0, tzinfo=UTC)
    for i in range(TARGET):
        u = everyone[i % len(everyone)]
        kind, title_t, body_t = templates[i % len(templates)]
        created = base + timedelta(days=i, hours=rng.randint(0, 10))
        session.add(
            Notification(
                id=det_uuid("notif", str(i)),
                user_id=u.id,
                kind=kind,
                title=title_t.format(n=rng.choice([5, 10, 20, 50])),
                body=body_t,
                data={"index": i},
                read_at=(created + timedelta(hours=2)) if rng.random() < 0.55 else None,
                created_at=created,
            )
        )
    await session.flush()
    log.info("bulk_notifications_ready")


# ---------------------------------------------------------------------------
# Wallet ledger (mirrors real reward credit entries)
# ---------------------------------------------------------------------------
async def seed_ledger(session: AsyncSession, students) -> None:
    from app.models.wallet import WalletAccount, WalletLedgerEntry

    existing_ids = {e for (e,) in (await session.execute(select(WalletLedgerEntry.id))).all()}
    accounts = {a.user_id: a for a in (await session.execute(select(WalletAccount))).scalars()}
    rng = random.Random(29)
    base = datetime(2025, 1, 3, 9, 0, tzinfo=UTC)
    made = 0
    for s in students:
        acc = accounts.get(s.id)
        if acc is None:
            continue
        balance = 0
        for j in range(4):
            amount = rng.choice([5, 10, 15, 20, 40, 60, 100])
            balance += amount
            created = base + timedelta(days=j * 30 + (made % 25))
            entry_id = det_uuid("ledger", str(s.id), str(j))
            if entry_id in existing_ids:
                continue
            existing_ids.add(entry_id)
            session.add(
                WalletLedgerEntry(
                    id=entry_id,
                    account_id=acc.id,
                    token_id=0,
                    entry_type="credit",
                    amount=amount,
                    balance_after=balance,
                    reference_type="reward",
                    reference_id=f"seed-{s.id}-{j}",
                    reward_key=None,
                    description="Hadiah aktivitas belajar.",
                    created_at=created,
                )
            )
            made += 1
        acc.cached_balance = balance
    await session.flush()
    log.info("bulk_ledger_ready", entries=made)


# ---------------------------------------------------------------------------
# Multiple-choice quiz (kept: referenced by tests) — real questions
# ---------------------------------------------------------------------------
async def _seed_mc_quiz(session: AsyncSession, teachers) -> None:
    """Seed one published multiple-choice quiz with real questions."""
    from app.models.exam import Exam, Question, QuestionOption

    title = "Kuis Pilihan Ganda — Pengetahuan Umum"
    exists = (
        await session.execute(select(Exam.id).where(Exam.title == title))
    ).scalar_one_or_none()
    if exists is not None:
        return
    owner = teachers[0]
    exam_id = det_uuid("exam", "mc-quiz")
    session.add(
        Exam(
            id=exam_id,
            title=title,
            owner_id=owner.id,
            duration_minutes=15,
            status="published",
            is_active=True,
            passing_score_bp=6000,
            instructions="Pilih satu jawaban yang paling tepat.",
        )
    )
    await session.flush()

    mc_items = [
        ("Ibu kota Indonesia adalah?", ["Jakarta", "Bandung", "Surabaya", "Medan"], 0),
        ("Planet terdekat dengan Matahari adalah?", ["Venus", "Merkurius", "Bumi", "Mars"], 1),
        ("Hasil dari 7 × 8 adalah?", ["54", "56", "48", "64"], 1),
        ("Lambang unsur kimia air adalah?", ["CO2", "O2", "H2O", "NaCl"], 2),
        ("Pulau terbesar di Indonesia adalah?", ["Jawa", "Sumatra", "Kalimantan", "Sulawesi"], 2),
    ]
    for pos, (prompt, choices, correct_idx) in enumerate(mc_items):
        qid = det_uuid("question", str(exam_id), str(pos))
        labels = "ABCDEFGH"
        session.add(
            Question(
                id=qid,
                exam_id=exam_id,
                owner_id=owner.id,
                prompt=prompt,
                correct_answer=labels[correct_idx],
                qtype="multiple_choice",
                position=pos,
                source="manual",
                review_status="approved",
            )
        )
        await session.flush()
        for oi, text in enumerate(choices):
            session.add(
                QuestionOption(
                    id=det_uuid("qopt", str(qid), str(oi)),
                    question_id=qid,
                    label=labels[oi],
                    text=text,
                    is_correct=(oi == correct_idx),
                    position=oi,
                )
            )
    await session.flush()
    log.info("bulk_mc_quiz_ready")


async def main() -> None:
    from app.db.session import session_scope
    from app.services.social_service import BadgeService

    log.info("seed_bulk_start")
    async with session_scope() as session:
        await BadgeService(session).ensure_catalog()
        teachers, students = await seed_accounts(session)
        await seed_badges(session)
        await seed_tasks(session, teachers, students)
        await seed_rooms(session, teachers, students)
        await seed_career(session, students)
        await seed_notifications(session, students, teachers)
        await seed_community(session, students)
        await seed_ledger(session, students)

        # Curriculum catalogue, then quests over those exams, then the monthly
        # learning history (100-200 records/mo) so quest entries land in months.
        from app.db import seed_timeline
        from app.models.exam import Exam

        await seed_timeline.seed_catalogue(session, teachers)
        exams = list(
            (await session.execute(select(Exam).where(Exam.status == "published"))).scalars().all()
        )
        await seed_quests(session, teachers, exams)
        await _seed_mc_quiz(session, teachers)
        await seed_timeline.seed_activity_timeline(session)
        await seed_timeline.seed_certificates_timeline(session)

        # Ops + blockchain + remaining small tables (realistic, dated).
        from app.db import seed_bulk_extra as extra

        await extra.seed_quest_outcomes(session, students)
        await extra.seed_progress_boards(session, students, teachers)
        await extra.seed_ops_tables(session, students, teachers)
        await extra.seed_misc(session, students, teachers)
    log.info("seed_bulk_done")


if __name__ == "__main__":
    asyncio.run(main())
