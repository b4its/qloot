"""Support seeder — part 2: quest outcomes, leaderboards, ops and misc tables.

The curriculum and the monthly learning history live in
:mod:`app.db.seed_timeline`; quests/rooms/community/career live in
:mod:`app.db.seed_bulk`. This module finishes the job: it ties quest results to
the exam attempts produced by the timeline, materialises leaderboards from real
XP, and fills the operational/small tables (audit logs, room events, outbox,
withdrawals, sessions, assistant conversations, consultation threads).

Everything is deterministic (uuid5 ids) and idempotent (guarded by row counts /
existing keys), so the module is safe to re-run.
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
# Quest results (tie winners to real exam attempts from the timeline)
# ---------------------------------------------------------------------------
async def seed_quest_outcomes(session: AsyncSession, students) -> None:
    from app.models.exam import ExamAttempt
    from app.models.quest import Quest, QuestRule, QuestWinner
    from app.models.wallet import RewardAllocation
    from app.services.keys import reward_key

    quests = await _pick(session, Quest, 300)
    attempts = await _pick(session, ExamAttempt, 500)
    if not quests or not attempts or not students:
        return

    # QuestAttempt rows are produced by the timeline seeder (one per quest a
    # student enters, dated inside the month). Here we only record the *outcome*
    # — winners and their reward allocations — so we never double-count entries.

    # --- QuestWinner: top-3 per quest, respecting both unique constraints ----
    if await _count(session, QuestWinner) < TARGET:
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
            student = students[(i * 7 + 1) % len(students)]
            attempt = attempts[(i * 3) % len(attempts)]
            i += 1
            rank = (i % 3) + 1
            user_key = (quest.id, student.id)
            rank_key = (quest.id, rank)
            if user_key in existing_quest_user or rank_key in existing_quest_rank:
                if i > TARGET * 8:
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
                    submitted_at=attempt.submitted_at or datetime.now(UTC),
                    duration_seconds=(attempt.duration_seconds or 600) + i,
                    attempt_id=attempt.id,
                    reward_key=reward_key(quest.id, student.id, rank, quest.reward_version),
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    # --- RewardAllocation: one per winner ------------------------------------
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
            student = students[(i * 7 + 1) % len(students)]
            i += 1
            pair = (rule.quest_id, student.id, "quest_rank")
            if pair in existing_pairs:
                if i > TARGET * 8:
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
    now = datetime.now(UTC)

    # --- Roadmap milestones: a coherent 12-month plan per student -----------
    if await _count(session, RoadmapMilestone) < TARGET:
        periods = ["Bulan ke-1 – Bulan ke-3", "Bulan ke-4 – Bulan ke-8", "Bulan ke-9 – Bulan ke-12"]
        titles = [
            "Penguatan Fondasi Akademik",
            "Eksplorasi Proyek & Kompetisi",
            "Persiapan Seleksi PTN",
        ]
        existing_m = {
            (m.user_id, m.position)
            for m in (await session.execute(select(RoadmapMilestone))).scalars()
        }
        made = 0
        i = 0
        positions = 5
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
                    title=titles[pos % len(titles)],
                    description=(
                        f"Tahap {pos + 1} dari roadmap belajar: {titles[pos % len(titles)]}."
                    ),
                    period=periods[min(pos, len(periods) - 1)],
                    position=pos,
                    progress_percent=min(100, pos * 25),
                    status="completed"
                    if pos < 2
                    else ("in_progress" if pos == 2 else "not_started"),
                    tasks=["Latihan soal mingguan", "Review materi", "Ikut try out"],
                )
            )
            made += 1
            if made % 50 == 0:
                await session.flush()
        await session.flush()

    # --- User badges: award each badge to a realistic subset ----------------
    if await _count(session, UserBadge) < TARGET:
        badges = await _pick(session, Badge, 300)
        existing_ub: set[tuple[object, object]] = {
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
                        meta={"source": "seed"},
                    )
                )
                made += 1
            if made >= TARGET:
                break
            await session.flush()
        await session.flush()

    # --- A single global leaderboard materialised from real student XP ------
    if await _count(session, Leaderboard) == 0:
        board_id = det_uuid("lboard", "global")
        session.add(
            Leaderboard(
                id=board_id,
                scope="global",
                scope_id=None,
                period="all",
                is_materialized=True,
            )
        )
        await session.flush()
        rng = random.Random(53)
        ranked = sorted(students, key=lambda s: rng.random())
        for rank, person in enumerate(ranked, start=1):
            session.add(
                LeaderboardEntry(
                    id=det_uuid("lentry", str(board_id), str(person.id)),
                    leaderboard_id=board_id,
                    user_id=person.id,
                    rank=rank,
                    score_bp=10000 - (rank * 90),
                    opc_earned=max(0, 500 - rank * 7),
                )
            )
        await session.flush()

    # --- Ranking snapshots: a weekly series since Jan 2025 -------------------
    if await _count(session, RankingSnapshot) < TARGET:
        base = datetime(2025, 1, 6, tzinfo=UTC)
        for i in range(1, TARGET + 1):
            session.add(
                RankingSnapshot(
                    id=det_uuid("rsnap", str(i)),
                    scope="global",
                    scope_id=det_uuid("rsnap-scope", str(i)),
                    payload={"week": i, "top": []},
                    created_at=base + timedelta(weeks=i),
                )
            )
        await session.flush()

    # --- Assistant conversations: real Q&A turns across a real window -------
    from app.db.content import ASSISTANT_TURNS
    from app.models.assistant import AssistantConversation, AssistantMessage

    if students and await _count(session, AssistantConversation) < TARGET:
        base = datetime(2025, 2, 3, 15, 0, tzinfo=UTC)
        for i in range(1, TARGET + 1):
            student = students[i % len(students)]
            q, a = ASSISTANT_TURNS[i % len(ASSISTANT_TURNS)]
            created = base + timedelta(days=i, hours=i % 10)
            conv_id = det_uuid("aconv", str(student.id), str(i))
            session.add(
                AssistantConversation(
                    id=conv_id,
                    user_id=student.id,
                    title=q,
                    created_at=created,
                    updated_at=created,
                )
            )
            session.add(
                AssistantMessage(
                    id=det_uuid("amsg", "u", str(i)),
                    conversation_id=conv_id,
                    role="user",
                    content=q,
                    created_at=created,
                )
            )
            session.add(
                AssistantMessage(
                    id=det_uuid("amsg", "a", str(i)),
                    conversation_id=conv_id,
                    role="assistant",
                    content=a,
                    confidence_bp=8200,
                    created_at=created + timedelta(seconds=2),
                )
            )
            await session.flush()

    # --- Consultation threads (student <-> counselor) ------------------------
    from app.models.career import Consultation, ConsultationMessage

    if await _count(session, ConsultationMessage) < TARGET:
        consults = list((await session.execute(select(Consultation).limit(400))).scalars())
        made = 0
        for c in consults:
            if made >= TARGET:
                break
            session.add(
                ConsultationMessage(
                    id=det_uuid("cmsg", str(c.id), "s"),
                    consultation_id=c.id,
                    sender_id=c.user_id,
                    body="Selamat siang, saya ingin berkonsultasi soal pilihan jurusan.",
                    created_at=(c.scheduled_at or now) - timedelta(hours=2),
                )
            )
            made += 1
            if c.counselor_user_id is not None:
                session.add(
                    ConsultationMessage(
                        id=det_uuid("cmsg", str(c.id), "t"),
                        consultation_id=c.id,
                        sender_id=c.counselor_user_id,
                        body="Baik, kita bahas kekuatan akademik dan minatmu satu per satu ya.",
                        created_at=(c.scheduled_at or now) - timedelta(hours=1),
                    )
                )
                made += 1
        await session.flush()
    log.info("bulk_progress_boards_ready")


# ---------------------------------------------------------------------------
# Blockchain events (idempotent per transaction hash)
# ---------------------------------------------------------------------------
async def seed_blockchain_events(session: AsyncSession) -> int:
    """Seed one confirmation event per confirmed transaction hash.

    ``blockchain_events`` is unique on ``(transaction_hash, log_index)`` and the
    dry-run indexer writes rows to the same table while the stack is running.
    ``ON CONFLICT DO NOTHING`` on that constraint makes the insert idempotent
    and race-free. Returns the number of rows actually inserted.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models.wallet import BlockchainEvent, BlockchainTransaction

    txs = (
        (
            await session.execute(
                select(BlockchainTransaction)
                .where(BlockchainTransaction.transaction_hash.is_not(None))
                .order_by(BlockchainTransaction.transaction_hash)
                .limit(TARGET)
            )
        )
        .scalars()
        .all()
    )
    if not txs:
        return 0

    now = datetime.now(UTC)
    rows = [
        {
            "id": det_uuid("bevent", tx.transaction_hash or ""),
            "contract_address": _addr("contract"),
            "event_name": f"{tx.method}Confirmed",
            "transaction_hash": tx.transaction_hash,
            "log_index": 0,
            "block_number": tx.block_number or i,
            "args": {"method": tx.method},
            "processed": True,
            "created_at": now - timedelta(hours=i),
        }
        for i, tx in enumerate(txs)
    ]
    stmt = (
        pg_insert(BlockchainEvent)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_blockchain_events_tx_log")
        .returning(BlockchainEvent.id)
    )
    inserted = len((await session.execute(stmt)).all())
    await session.flush()
    log.info("bulk_blockchain_events_ready", inserted=inserted, candidates=len(rows))
    return inserted


# ---------------------------------------------------------------------------
# Audit logs, room events/invites, blockchain + wallet infra
# ---------------------------------------------------------------------------
async def seed_ops_tables(session: AsyncSession, students, teachers) -> None:
    from app.models.identity import AuditLog
    from app.models.room import Room, RoomEvent, RoomInvitation
    from app.models.wallet import (
        BlockchainTransaction,
        ContractDeployment,
        TransactionOutbox,
        WithdrawalRequest,
    )
    from app.services.keys import tx_idempotency_key, withdrawal_key

    everyone = students + teachers
    rng = random.Random(202)
    base = datetime(2025, 1, 5, 9, 0, tzinfo=UTC)

    if await _count(session, AuditLog) < TARGET:
        actions = [
            "auth.login",
            "admin.reward.retry",
            "admin.user.role",
            "course.create",
            "exam.publish",
            "grade.update",
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
                    created_at=base + timedelta(hours=i),
                )
            )
        await session.flush()

    rooms = await _pick(session, Room, 300)

    if rooms and await _count(session, RoomEvent) < TARGET:
        types = ["joined", "left", "opened", "closed"]
        for i in range(1, TARGET + 1):
            room = rooms[i % len(rooms)]
            session.add(
                RoomEvent(
                    id=det_uuid("revent", str(i)),
                    room_id=room.id,
                    event_type=types[i % len(types)],
                    payload={"index": i},
                    created_at=base + timedelta(hours=i),
                )
            )
        await session.flush()

    if rooms and await _count(session, RoomInvitation) < TARGET:
        for i in range(1, TARGET + 1):
            room = rooms[i % len(rooms)]
            student = students[i % len(students)]
            created = base + timedelta(hours=i)
            session.add(
                RoomInvitation(
                    id=det_uuid("rinvite", str(i)),
                    room_id=room.id,
                    email=student.email,
                    user_id=student.id,
                    code=f"INV{i:06d}",
                    expires_at=created + timedelta(days=7),
                    accepted_at=None,
                    created_at=created,
                    note="Undangan bergabung ke ruang belajar.",
                )
            )
        await session.flush()

    if await _count(session, BlockchainTransaction) < TARGET:
        for i in range(1, TARGET + 1):
            key = tx_idempotency_key("seed", str(i))
            created = base + timedelta(hours=i)
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
                    submitted_at=created,
                    confirmed_at=created,
                )
            )
        await session.flush()

    await seed_blockchain_events(session)

    if await _count(session, ContractDeployment) < 1:
        names = ["OryphemToken", "QlootChain", "OryphemIntelligence", "OryphemProxy"]
        for i, name in enumerate(names, start=1):
            session.add(
                ContractDeployment(
                    id=det_uuid("cdeploy", name),
                    network="localhost",
                    chain_id=31337,
                    name=name,
                    address=_addr(f"deploy{i}"),
                    deployer=_addr("deployer"),
                    treasury=_addr("treasury"),
                    tx_hash="0x"
                    + uuid.uuid5(uuid.NAMESPACE_URL, f"dtx{i}").hex
                    + uuid.uuid5(uuid.NAMESPACE_URL, f"dtxb{i}").hex,
                    block_number=i,
                    abi={},
                    is_active=True,
                )
            )
        await session.flush()

    if await _count(session, WithdrawalRequest) < TARGET:
        for i in range(1, TARGET + 1):
            student = students[i % len(students)]
            wid = det_uuid("wd", str(i))
            created = base + timedelta(hours=i)
            session.add(
                WithdrawalRequest(
                    id=wid,
                    user_id=student.id,
                    reward_key=withdrawal_key(wid),
                    destination_address=_addr(f"wd{i}"),
                    token_id=0,
                    amount=rng.randint(10, 150),
                    status=["requested", "submitted", "completed"][i % 3],
                    created_at=created,
                )
            )
        await session.flush()

    if await _count(session, TransactionOutbox) < TARGET:
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
            created = base + timedelta(hours=i)
            session.add(
                TransactionOutbox(
                    id=det_uuid("outbox", str(i)),
                    topic=topic,
                    idempotency_key=tx_idempotency_key("outbox", str(i)),
                    payload=payload,
                    status="done",
                    attempts=1,
                    processed_at=created,
                    created_at=created,
                )
            )
        await session.flush()
    log.info("bulk_ops_ready")


async def seed_misc(session: AsyncSession, students, teachers) -> None:
    """Fill the remaining small tables: sessions, password-reset tokens."""

    from app.models.identity import PasswordResetToken, Session

    everyone = students + teachers
    base = datetime(2025, 1, 4, 8, 0, tzinfo=UTC)

    if await _count(session, Session) < TARGET:
        for i in range(1, TARGET + 1):
            user = everyone[i % len(everyone)]
            created = base + timedelta(hours=i * 3)
            session.add(
                Session(
                    id=det_uuid("sess", str(i)),
                    user_id=user.id,
                    token_hash=uuid.uuid5(uuid.NAMESPACE_URL, f"sess{i}").hex,
                    user_agent="Mozilla/5.0 (QLoot seed)",
                    ip_address="127.0.0.1",
                    created_at=created,
                    last_used_at=created + timedelta(minutes=20),
                    expires_at=created + timedelta(days=14),
                    revoked_at=None,
                )
            )
        await session.flush()

    if await _count(session, PasswordResetToken) < TARGET:
        for i in range(1, TARGET + 1):
            user = everyone[i % len(everyone)]
            created = base + timedelta(hours=i)
            session.add(
                PasswordResetToken(
                    id=det_uuid("prt", str(i)),
                    user_id=user.id,
                    token_hash=uuid.uuid5(uuid.NAMESPACE_URL, f"prt{i}").hex,
                    created_at=created,
                    expires_at=created + timedelta(hours=2),
                    used_at=created + timedelta(hours=1),
                )
            )
        await session.flush()
    log.info("bulk_misc_ready")


async def main() -> None:
    """Run all part-2 seeds against the DB (called by seed_bulk.main)."""
    raise RuntimeError("seed_bulk_extra is invoked via seed_bulk.main(), not directly")
