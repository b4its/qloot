"""Bulk seeder — part 2: fill the remaining tables to >= 200 rows each.

``seed_bulk.py`` covers the "content" tables. This module fills the rest of
the schema — attempts, answers, grading, certificates, quest winners, rewards,
leaderboards, audit logs, room invitations/events, withdrawals and the
blockchain tables — so *every* table has a realistic volume for the demo.

All inserts are deterministic (uuid5 ids) and idempotent (guarded by a row
count), so the module is safe to re-run.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.seed_bulk import TARGET, det_uuid

log = get_logger("seed_bulk_extra")


async def _count(session: AsyncSession, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _pick(session: AsyncSession, model, limit: int = 300) -> list:
    return list((await session.execute(select(model).limit(limit))).scalars().all())


def _addr(seed: str) -> str:
    return "0x" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:40]


# ---------------------------------------------------------------------------
# Attempts -> answers -> grading -> question options
# ---------------------------------------------------------------------------
async def seed_attempts_and_grading(session: AsyncSession, students) -> None:
    from app.models.exam import (
        Exam,
        ExamAttempt,
        GradingJob,
        GradingResult,
        Question,
        QuestionOption,
        StudentAnswer,
    )
    from app.services.keys import tx_idempotency_key

    exams = await _pick(session, Exam, 300)
    if not exams or not students:
        return
    questions = await _pick(session, Question, 1000)
    q_by_exam: dict[uuid.UUID, list[Question]] = {}
    for q in questions:
        if q.exam_id:
            q_by_exam.setdefault(q.exam_id, []).append(q)

    # --- exam_attempts -----------------------------------------------------
    if await _count(session, ExamAttempt) < TARGET:
        rng = random.Random(101)
        for i in range(1, TARGET + 1):
            exam = exams[i % len(exams)]
            student = students[i % len(students)]
            score = rng.randint(4000, 10000)
            now = datetime.now(UTC) - timedelta(hours=i)
            session.add(
                ExamAttempt(
                    id=det_uuid("attempt", str(i)),
                    exam_id=exam.id,
                    user_id=student.id,
                    attempt_number=1,
                    status="graded",
                    score_bp=score,
                    passed=score >= exam.passing_score_bp,
                    started_at=now - timedelta(seconds=1800),
                    submitted_at=now,
                    graded_at=now,
                    duration_seconds=rng.randint(300, 1700),
                )
            )
            if i % 50 == 0:
                await session.flush()
        await session.flush()

    attempts = await _pick(session, ExamAttempt, 400)

    # --- student_answers (>= 200) -----------------------------------------
    if await _count(session, StudentAnswer) < TARGET:
        # Existing (attempt, question) pairs so we never violate the unique key.
        existing_pairs = {
            (a.attempt_id, a.question_id)
            for a in (await session.execute(select(StudentAnswer))).scalars()
        }
        made = 0
        for i, attempt in enumerate(attempts):
            qs = q_by_exam.get(attempt.exam_id, [])
            if not qs:
                continue
            q = qs[i % len(qs)]
            pair = (attempt.id, q.id)
            if pair in existing_pairs:
                continue
            existing_pairs.add(pair)
            session.add(
                StudentAnswer(
                    id=det_uuid("sanswer", str(attempt.id), str(q.id)),
                    attempt_id=attempt.id,
                    question_id=q.id,
                    answer_text="Jawaban simulasi siswa untuk soal ini.",
                    score_bp=attempt.score_bp,
                    max_score_bp=q.max_score_bp,
                    feedback="Umpan balik AI (simulasi).",
                    similarity_bp=(attempt.score_bp or 0),
                    graded_at=datetime.now(UTC),
                )
            )
            made += 1
            if made >= TARGET:
                break
        await session.flush()

    # --- grading_jobs + grading_results (>= 200) ---------------------------
    if await _count(session, GradingJob) < TARGET:
        # One job per attempt is enforced by uq_grading_jobs_attempt, and the
        # demo seed already creates jobs for some attempts — skip those.
        existing_attempts = {
            j.attempt_id
            for j in (await session.execute(select(GradingJob))).scalars()
            if j.attempt_id is not None
        }
        made = 0
        for attempt in attempts:
            if attempt.id in existing_attempts:
                continue
            existing_attempts.add(attempt.id)
            session.add(
                GradingJob(
                    id=det_uuid("gjob", str(attempt.id)),
                    attempt_id=attempt.id,
                    owner_id=attempt.user_id,
                    exam_id=attempt.exam_id,
                    kind="grading",
                    status="done",
                    attempts=1,
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                )
            )
            made += 1
            if made >= TARGET:
                break
        await session.flush()

    if await _count(session, GradingResult) < TARGET:
        jobs = await _pick(session, GradingJob, 300)
        existing_jobs = {r.job_id for r in (await session.execute(select(GradingResult))).scalars()}
        made = 0
        for job in jobs:
            if job.attempt_id is None or job.id in existing_jobs:
                continue
            existing_jobs.add(job.id)
            session.add(
                GradingResult(
                    id=det_uuid("gres", str(job.id)),
                    job_id=job.id,
                    attempt_id=job.attempt_id,
                    model="mock",
                    raw={"score_bp": 8000, "passed": True},
                )
            )
            made += 1
            if made >= TARGET:
                break
        await session.flush()

    # --- question_options (>= 200) ----------------------------------------
    if await _count(session, QuestionOption) < TARGET:
        made = 0
        for q in questions:
            # Options only make sense for multiple-choice questions.
            q.qtype = "multiple_choice"
            q.correct_answer = "A"
            for label, text, correct in (
                ("A", "Pilihan pertama (benar)", True),
                ("B", "Pilihan kedua", False),
                ("C", "Pilihan ketiga", False),
            ):
                session.add(
                    QuestionOption(
                        id=det_uuid("qopt", str(q.id), label),
                        question_id=q.id,
                        label=label,
                        text=text,
                        is_correct=correct,
                        position=ord(label) - ord("A"),
                    )
                )
                made += 1
                if made >= TARGET:
                    break
            if made >= TARGET:
                break
        await session.flush()
        _ = tx_idempotency_key  # keep import used if branch skipped

    log.info("bulk_attempts_ready")


# ---------------------------------------------------------------------------
# Lesson progress -> certificates
# ---------------------------------------------------------------------------
async def seed_progress_and_certificates(session: AsyncSession, students) -> None:
    from app.models.certificate import Certificate
    from app.models.learning import Course, Lesson, LessonProgress

    lessons = await _pick(session, Lesson, 400)
    if not lessons or not students:
        return
    lesson_by_course: dict[uuid.UUID, list[Lesson]] = {}
    for lesson in lessons:
        lesson_by_course.setdefault(lesson.course_id, []).append(lesson)

    if await _count(session, LessonProgress) < TARGET:
        existing_lp = {
            (p.user_id, p.lesson_id)
            for p in (await session.execute(select(LessonProgress))).scalars()
        }
        made = 0
        i = 0
        while made < TARGET and lessons:
            lesson = lessons[i % len(lessons)]
            student = students[i % len(students)]
            i += 1
            key = (student.id, lesson.id)
            if key in existing_lp:
                if i > TARGET * 8:
                    break
                continue
            existing_lp.add(key)
            session.add(
                LessonProgress(
                    id=det_uuid("lprog", str(student.id), str(lesson.id)),
                    user_id=student.id,
                    lesson_id=lesson.id,
                    course_id=lesson.course_id,
                    progress_percent=100,
                    completed=True,
                    completed_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    if await _count(session, Certificate) < TARGET:
        courses = await _pick(session, Course, 300)
        existing_c = {
            (c.user_id, c.course_id) for c in (await session.execute(select(Certificate))).scalars()
        }
        made = 0
        i = 0
        while made < TARGET and courses:
            course = courses[i % len(courses)]
            student = students[i % len(students)]
            i += 1
            key = (student.id, course.id)
            if key in existing_c:
                if i > TARGET * 8:
                    break
                continue
            existing_c.add(key)
            cred = f"QLT-{abs(hash(str(course.id))) % 9999:04d}-{made:04d}"
            session.add(
                Certificate(
                    id=det_uuid("cert", str(student.id), str(course.id)),
                    user_id=student.id,
                    course_id=course.id,
                    credential_id=cred,
                    verification_hash=uuid.uuid5(uuid.NAMESPACE_URL, cred).hex[:32],
                    course_title=course.title,
                    recipient_name=student.full_name,
                    issued_by="QLoot Academy",
                    edition_number=made + 1,
                    edition_total=5000,
                    issued_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()
    log.info("bulk_progress_certs_ready")


# ---------------------------------------------------------------------------
# Quest attempts / winners / rewards
# ---------------------------------------------------------------------------
async def seed_quest_outcomes(session: AsyncSession, students) -> None:
    from app.models.exam import ExamAttempt
    from app.models.quest import Quest, QuestAttempt, QuestRule, QuestWinner
    from app.models.wallet import RewardAllocation
    from app.services.keys import reward_key

    quests = await _pick(session, Quest, 300)
    attempts = await _pick(session, ExamAttempt, 400)
    if not quests or not attempts or not students:
        return

    if await _count(session, QuestAttempt) < TARGET:
        existing = {
            (a.quest_id, a.user_id) for a in (await session.execute(select(QuestAttempt))).scalars()
        }
        made = 0
        i = 0
        while made < TARGET and quests:
            quest = quests[i % len(quests)]
            student = students[i % len(students)]
            attempt = attempts[i % len(attempts)]
            i += 1
            key = (quest.id, student.id)
            if key in existing:
                if i > TARGET * 6:
                    break
                continue
            existing.add(key)
            session.add(
                QuestAttempt(
                    id=det_uuid("qattempt", str(quest.id), str(student.id)),
                    quest_id=quest.id,
                    user_id=student.id,
                    exam_attempt_id=attempt.id,
                    submitted_at=datetime.now(UTC) - timedelta(hours=i),
                    score_bp=attempt.score_bp,
                    is_valid=True,
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    if await _count(session, QuestWinner) < TARGET:
        # QuestWinner is unique on (quest_id, user_id) AND (quest_id, rank),
        # so track both pairs and skip any combination that already exists.
        existing_quest_user = {
            (w.quest_id, w.user_id) for w in (await session.execute(select(QuestWinner))).scalars()
        }
        existing_quest_rank = {
            (w.quest_id, w.rank) for w in (await session.execute(select(QuestWinner))).scalars()
        }
        made = 0
        i = 0
        while made < TARGET and quests:
            quest = quests[i % len(quests)]
            student = students[i % len(students)]
            attempt = attempts[i % len(attempts)]
            i += 1
            rank = (i % 3) + 1
            user_key = (quest.id, student.id)
            rank_key = (quest.id, rank)
            if user_key in existing_quest_user or rank_key in existing_quest_rank:
                if i > TARGET * 6:
                    break
                continue
            existing_quest_user.add(user_key)
            existing_quest_rank.add(rank_key)
            session.add(
                QuestWinner(
                    id=det_uuid("qwinner", str(quest.id), str(student.id)),
                    quest_id=quest.id,
                    user_id=student.id,
                    rank=rank,
                    score_bp=attempt.score_bp or 8000,
                    submitted_at=datetime.now(UTC) - timedelta(hours=i),
                    duration_seconds=600 + i,
                    attempt_id=attempt.id,
                    reward_key=reward_key(quest.id, student.id, rank, 1),
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    if await _count(session, RewardAllocation) < TARGET:
        rules = await _pick(session, QuestRule, 600)
        existing_pairs = {
            (a.quest_id, a.user_id, a.reward_type)
            for a in (await session.execute(select(RewardAllocation))).scalars()
        }
        made = 0
        i = 0
        while made < TARGET and rules:
            rule = rules[i % len(rules)]
            student = students[i % len(students)]
            i += 1
            pair = (rule.quest_id, student.id, "quest_rank")
            if pair in existing_pairs:
                if i > TARGET * 6:
                    break
                continue
            existing_pairs.add(pair)
            rk = reward_key(rule.quest_id, student.id, rule.rank, 1)
            session.add(
                RewardAllocation(
                    id=det_uuid("ralloc", str(rule.id), str(student.id)),
                    reward_key=rk,
                    user_id=student.id,
                    quest_id=rule.quest_id,
                    reward_type="quest_rank",
                    rank=rule.rank,
                    amount=rule.reward_amount,
                    status="confirmed" if made % 3 else "pending",
                    confirmed_at=datetime.now(UTC) if made % 3 else None,
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()
    log.info("bulk_quest_outcomes_ready")


# ---------------------------------------------------------------------------
# Milestones, user badges, leaderboards, ranking snapshots
# ---------------------------------------------------------------------------
async def seed_progress_boards(session: AsyncSession, students, teachers) -> None:
    from app.models.career import RoadmapMilestone
    from app.models.ranking import Leaderboard, LeaderboardEntry, RankingSnapshot
    from app.models.social import Badge, UserBadge

    everyone = students + teachers

    if await _count(session, RoadmapMilestone) < TARGET:
        periods = ["Bulan ke-1 – Bulan ke-3", "Bulan ke-4 – Bulan ke-8", "Bulan ke-9 – Bulan ke-12"]
        titles = ["Penguatan Fondasi", "Eksplorasi Proyek", "Persiapan Seleksi PTN"]
        # 5 positions per student so 50 students x 5 = 250 unique (user, position).
        positions = 5
        existing_m = {
            (m.user_id, m.position)
            for m in (await session.execute(select(RoadmapMilestone))).scalars()
        }
        made = 0
        i = 0
        while made < TARGET and students:
            student = students[i % len(students)]
            pos = (i // len(students)) % positions
            i += 1
            key = (student.id, pos)
            if key in existing_m:
                if i > TARGET * 8:
                    break
                continue
            existing_m.add(key)
            session.add(
                RoadmapMilestone(
                    id=det_uuid("mile", str(student.id), str(pos)),
                    user_id=student.id,
                    title=f"{titles[pos % len(titles)]} ({pos + 1})",
                    description="Tonggak roadmap (simulasi).",
                    period=periods[pos % len(periods)],
                    position=pos,
                    progress_percent=(pos * 20) % 100,
                    status="not_started" if pos else "in_progress",
                    tasks=["Latihan soal", "Review materi"],
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    if await _count(session, UserBadge) < TARGET:
        badges = await _pick(session, Badge, 300)
        existing_ub = {
            (b.user_id, b.badge_id) for b in (await session.execute(select(UserBadge))).scalars()
        }
        made = 0
        for badge in badges:
            for person in everyone:
                if made >= TARGET:
                    break
                key = (person.id, badge.id)
                if key in existing_ub:
                    continue
                existing_ub.add(key)
                session.add(
                    UserBadge(
                        id=det_uuid("ubadge", str(person.id), str(badge.id)),
                        user_id=person.id,
                        badge_id=badge.id,
                        meta={"seed": True},
                    )
                )
                made += 1
            if made >= TARGET:
                break
            await session.flush()
        await session.flush()

    if await _count(session, Leaderboard) < TARGET:
        scopes = ["global", "room", "quest"]
        for i in range(1, TARGET + 1):
            scope = scopes[i % len(scopes)]
            session.add(
                Leaderboard(
                    id=det_uuid("lboard", str(i)),
                    scope=scope,
                    scope_id=det_uuid("lboard-scope", str(i)) if scope != "global" else None,
                    period="all",
                    is_materialized=True,
                )
            )
        await session.flush()

    if await _count(session, LeaderboardEntry) < TARGET:
        boards = await _pick(session, Leaderboard, 300)
        existing_le = {
            (e.leaderboard_id, e.user_id)
            for e in (await session.execute(select(LeaderboardEntry))).scalars()
        }
        made = 0
        for board in boards:
            for person in everyone:
                if made >= TARGET:
                    break
                key = (board.id, person.id)
                if key in existing_le:
                    continue
                existing_le.add(key)
                session.add(
                    LeaderboardEntry(
                        id=det_uuid("lentry", str(board.id), str(person.id)),
                        leaderboard_id=board.id,
                        user_id=person.id,
                        rank=made + 1,
                        score_bp=(made * 137) % 10000,
                        opc_earned=made % 200,
                    )
                )
                made += 1
            if made >= TARGET:
                break
            await session.flush()
        await session.flush()

    if await _count(session, RankingSnapshot) < TARGET:
        for i in range(1, TARGET + 1):
            session.add(
                RankingSnapshot(
                    id=det_uuid("rsnap", str(i)),
                    scope=["global", "room", "quest"][i % 3],
                    scope_id=det_uuid("rsnap-scope", str(i)),
                    payload={"entries": [], "index": i},
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()
    log.info("bulk_progress_boards_ready")


# ---------------------------------------------------------------------------
# Audit logs, room events/invites, blockchain + wallet infra
# ---------------------------------------------------------------------------
async def seed_ops_tables(session: AsyncSession, students, teachers) -> None:
    from app.models.identity import AuditLog
    from app.models.room import Room, RoomEvent, RoomInvitation
    from app.models.wallet import (
        BlockchainEvent,
        BlockchainTransaction,
        ContractDeployment,
        TransactionOutbox,
        WithdrawalRequest,
    )
    from app.services.keys import tx_idempotency_key, withdrawal_key

    everyone = students + teachers
    rng = random.Random(202)

    if await _count(session, AuditLog) < TARGET:
        actions = [
            "auth.login",
            "admin.reward.retry",
            "admin.user.role",
            "course.create",
            "exam.publish",
        ]
        for i in range(1, TARGET + 1):
            actor = everyone[i % len(everyone)]
            session.add(
                AuditLog(
                    id=det_uuid("audit", str(i)),
                    actor_id=actor.id,
                    action=actions[i % len(actions)],
                    entity_type="seed",
                    entity_id=str(i),
                    request_id=uuid.uuid5(uuid.NAMESPACE_URL, f"req{i}").hex[:16],
                    data={"index": i},
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()

    rooms = await _pick(session, Room, 300)

    if await _count(session, RoomEvent) < TARGET:
        types = ["joined", "left", "opened", "closed"]
        for i in range(1, TARGET + 1):
            room = rooms[i % len(rooms)]
            session.add(
                RoomEvent(
                    id=det_uuid("revent", str(i)),
                    room_id=room.id,
                    event_type=types[i % len(types)],
                    payload={"index": i},
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()

    if await _count(session, RoomInvitation) < TARGET:
        for i in range(1, TARGET + 1):
            room = rooms[i % len(rooms)]
            student = students[i % len(students)]
            session.add(
                RoomInvitation(
                    id=det_uuid("rinvite", str(i)),
                    room_id=room.id,
                    email=student.email,
                    user_id=student.id,
                    code=f"INV{i:06d}",
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                    accepted_at=None,
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                    note="Undangan simulasi.",
                )
            )
        await session.flush()

    # --- blockchain_transactions ------------------------------------------
    if await _count(session, BlockchainTransaction) < TARGET:
        for i in range(1, TARGET + 1):
            key = tx_idempotency_key("seed", str(i))
            session.add(
                BlockchainTransaction(
                    id=det_uuid("btx", str(i)),
                    idempotency_key=key,
                    network="localhost",
                    chain_id=31337,
                    from_address=_addr(f"from{i}"),
                    to_address=_addr(f"to{i}"),
                    method=["rewardUser", "mint", "burn", "swapOptFor"][i % 4],
                    arguments={"index": i},
                    transaction_hash="0x"
                    + uuid.uuid5(uuid.NAMESPACE_URL, f"tx{i}").hex
                    + uuid.uuid5(uuid.NAMESPACE_URL, f"txb{i}").hex,
                    block_number=i,
                    confirmation_count=2,
                    status="confirmed",
                    submitted_at=datetime.now(UTC) - timedelta(hours=i),
                    confirmed_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()

    if await _count(session, BlockchainEvent) < TARGET:
        txs = await _pick(session, BlockchainTransaction, 300)
        for i, tx in enumerate(txs[:TARGET]):
            if not tx.transaction_hash:
                continue
            session.add(
                BlockchainEvent(
                    id=det_uuid("bevent", str(i)),
                    contract_address=_addr("contract"),
                    event_name=f"{tx.method}Confirmed",
                    transaction_hash=tx.transaction_hash,
                    log_index=0,
                    block_number=tx.block_number or i,
                    args={"method": tx.method},
                    processed=True,
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()

    if await _count(session, ContractDeployment) < TARGET:
        # The four QLoot contracts (each its own UUPS proxy).
        names = ["OryphemToken", "QlootChain", "OryphemIntelligence", "OryphemProxy"]
        for i in range(1, TARGET + 1):
            session.add(
                ContractDeployment(
                    id=det_uuid("cdeploy", str(i)),
                    network=f"seed-net-{i}",
                    chain_id=31337,
                    name=names[(i - 1) % len(names)],
                    address=_addr(f"deploy{i}"),
                    deployer=_addr("deployer"),
                    treasury=_addr("treasury"),
                    tx_hash="0x"
                    + uuid.uuid5(uuid.NAMESPACE_URL, f"dtx{i}").hex
                    + uuid.uuid5(uuid.NAMESPACE_URL, f"dtxb{i}").hex,
                    block_number=i,
                    abi={},
                    is_active=i == 1,
                )
            )
        await session.flush()

    if await _count(session, WithdrawalRequest) < TARGET:
        for i in range(1, TARGET + 1):
            student = students[i % len(students)]
            wid = det_uuid("wd", str(i))
            session.add(
                WithdrawalRequest(
                    id=wid,
                    user_id=student.id,
                    reward_key=withdrawal_key(wid),
                    destination_address=_addr(f"wd{i}"),
                    token_id=0,
                    amount=rng.randint(5, 200),
                    status=["requested", "submitted", "completed"][i % 3],
                )
            )
        await session.flush()

    if await _count(session, TransactionOutbox) < TARGET:
        # Topic-appropriate payloads so a seeded row is realistic. All rows are
        # seeded as "done" so the worker never re-processes them.
        samples = [
            ("reward", {"reward_key": "seed-rk", "amount": 50, "asset": "OPT"}),
            ("airdrop", {"to": _addr("airdrop"), "amount": 10, "asset": "ORT"}),
            (
                "withdrawal",
                {"withdrawal_id": str(det_uuid("wd", "1")), "amount": 25, "asset": "OPT"},
            ),
            ("pause", {"action": "pause", "asset": "OPT"}),
            ("swap", {"asset": "ORT", "amount": 5, "opt_cost": 250}),
            ("ai_request", {"requests": 1}),
        ]
        for i in range(1, TARGET + 1):
            topic, payload = samples[i % len(samples)]
            session.add(
                TransactionOutbox(
                    id=det_uuid("outbox", str(i)),
                    topic=topic,
                    idempotency_key=tx_idempotency_key("outbox", str(i)),
                    payload=payload,
                    status="done",
                    attempts=1,
                    processed_at=datetime.now(UTC) - timedelta(hours=i),
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()
    log.info("bulk_ops_ready")


async def seed_misc(session: AsyncSession, students, teachers) -> None:
    """Fill the remaining small tables: sessions, task completions, career
    recommendations and password-reset tokens."""
    from app.models.career import CareerRecommendation
    from app.models.identity import PasswordResetToken, Session
    from app.models.quest import Task, TaskCompletion
    from app.services.keys import task_reward_key

    everyone = students + teachers

    if await _count(session, Session) < TARGET:
        for i in range(1, TARGET + 1):
            user = everyone[i % len(everyone)]
            session.add(
                Session(
                    id=det_uuid("sess", str(i)),
                    user_id=user.id,
                    token_hash=uuid.uuid5(uuid.NAMESPACE_URL, f"sess{i}").hex,
                    user_agent="Mozilla/5.0 (seed)",
                    ip_address="127.0.0.1",
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                    last_used_at=datetime.now(UTC) - timedelta(hours=i),
                    expires_at=datetime.now(UTC) + timedelta(days=14),
                    revoked_at=None,
                )
            )
        await session.flush()

    if await _count(session, TaskCompletion) < TARGET:
        tasks = await _pick(session, Task, 300)
        existing_tc = {
            (t.task_id, t.user_id, t.period_key)
            for t in (await session.execute(select(TaskCompletion))).scalars()
        }
        made = 0
        for task in tasks:
            for person in students:
                if made >= TARGET:
                    break
                key = (task.id, person.id, "")
                if key in existing_tc:
                    continue
                existing_tc.add(key)
                session.add(
                    TaskCompletion(
                        id=det_uuid("tcomp", str(task.id), str(person.id)),
                        task_id=task.id,
                        user_id=person.id,
                        period_key="",
                        reward_key=task_reward_key(task.id, person.id, ""),
                        completed_at=datetime.now(UTC) - timedelta(hours=made),
                    )
                )
                made += 1
            if made >= TARGET:
                break
        await session.flush()

    if await _count(session, CareerRecommendation) < TARGET:
        majors = ["Teknik Elektro", "Ilmu Komputer", "Kedokteran", "Akuntansi", "Psikologi"]
        made = 0
        i = 0
        while made < TARGET and students:
            student = students[i % len(students)]
            rank = (i // len(students)) % 3 + 1
            major = majors[rank % len(majors)]
            i += 1
            key = (student.id, major, rank)
            # CI-04: vary the status so every state the UI renders has data.
            # A third stay draft, a third are in_review, a third approved.
            status = ["draft", "in_review", "approved"][i % 3]
            session.add(
                CareerRecommendation(
                    id=det_uuid("crec", str(student.id), major, str(rank), str(i)),
                    user_id=student.id,
                    major=major,
                    fit_score=60 + (i % 35),
                    academic_fit=60 + (i % 30),
                    personality_fit=60 + (i % 25),
                    rationale="Rekomendasi simulasi.",
                    universities=["ITB", "UI"],
                    admission_paths=["SNBP", "SNBT"],
                    skills=["Analisis", "Komunikasi"],
                    careers=["Engineer", "Analyst"],
                    rank=rank,
                    status=status,
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
            _ = key
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    if await _count(session, PasswordResetToken) < TARGET:
        for i in range(1, TARGET + 1):
            user = everyone[i % len(everyone)]
            session.add(
                PasswordResetToken(
                    id=det_uuid("prt", str(i)),
                    user_id=user.id,
                    token_hash=uuid.uuid5(uuid.NAMESPACE_URL, f"prt{i}").hex,
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                    expires_at=datetime.now(UTC) - timedelta(hours=i - 1),
                    used_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
        await session.flush()

    # CARE-01: give students assistant conversations with a couple of turns so
    # the history UI has demo data.
    from app.models.assistant import AssistantConversation, AssistantMessage

    if await _count(session, AssistantConversation) < TARGET and students:
        prompts = [
            ("Bedanya SNBP dan SNBT?", "SNBP tanpa tes, SNBT lewat UTBK."),
            ("Prospek Ilmu Komputer?", "Software Engineer, Data Scientist, AI Engineer."),
            ("Jurusan untuk IPA?", "Teknik, Kedokteran, atau Sains murni."),
        ]
        for i in range(1, TARGET + 1):
            student = students[i % len(students)]
            q, a = prompts[i % len(prompts)]
            conv_id = det_uuid("aconv", str(student.id), str(i))
            session.add(
                AssistantConversation(
                    id=conv_id,
                    user_id=student.id,
                    title=q,
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                    updated_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
            session.add(
                AssistantMessage(
                    id=det_uuid("amsg", "u", str(i)),
                    conversation_id=conv_id,
                    role="user",
                    content=q,
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
            session.add(
                AssistantMessage(
                    id=det_uuid("amsg", "a", str(i)),
                    conversation_id=conv_id,
                    role="assistant",
                    content=a,
                    confidence_bp=8000,
                    created_at=datetime.now(UTC) - timedelta(hours=i) + timedelta(seconds=1),
                )
            )
        await session.flush()

    # CARE-06: consultation threads so the BK panel has demo conversations.
    from app.models.career import Consultation, ConsultationMessage

    if await _count(session, ConsultationMessage) < TARGET:
        consults = list((await session.execute(select(Consultation).limit(400))).scalars())
        for i, c in enumerate(consults[: TARGET // 2]):
            session.add(
                ConsultationMessage(
                    id=det_uuid("cmsg", str(c.id), "s", str(i)),
                    consultation_id=c.id,
                    sender_id=c.user_id,
                    body="Terima kasih, saya ingin bertanya soal jurusan.",
                    created_at=datetime.now(UTC) - timedelta(hours=i),
                )
            )
            if c.counselor_user_id is not None:
                session.add(
                    ConsultationMessage(
                        id=det_uuid("cmsg", str(c.id), "t", str(i)),
                        consultation_id=c.id,
                        sender_id=c.counselor_user_id,
                        body="Siap, kita bahas pada sesi berikutnya ya.",
                        created_at=datetime.now(UTC) - timedelta(hours=i) + timedelta(minutes=5),
                    )
                )
        await session.flush()
    log.info("bulk_misc_ready")


async def main() -> None:
    """Run all part-2 seeds against the DB (called by seed_bulk.main)."""
    raise RuntimeError("seed_bulk_extra is invoked via seed_bulk.main(), not directly")
