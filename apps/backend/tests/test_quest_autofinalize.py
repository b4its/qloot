"""Auto-finalize worker sweep for quests past their closes_at (GAME-01).

A quest with a past closes_at must not require a manual teacher click to
distribute rewards/notifications/badges — a periodic sweep should finalize it
transactionally and idempotently, exactly like the manual HTTP endpoint does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Exam, ExamAttempt, User
from app.models.quest import QuestWinner
from app.models.social import Notification
from app.models.wallet import WalletAccount, WalletLedgerEntry
from app.services.quest_service import QuestService

pytestmark = pytest.mark.integration


async def _user(session, email, role="student") -> User:
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models.identity import Role, UserRole

    role_row = (await session.execute(select(Role).where(Role.name == role))).scalar_one()
    u = User(
        email=email,
        full_name="Test User",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:64],
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role_row.id))
    await session.flush()
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == u.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def _graded_attempt(session, exam, user, score_bp, seconds):
    now = datetime.now(UTC)
    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        attempt_number=1,
        status="graded",
        score_bp=score_bp,
        passed=score_bp >= 6000,
        started_at=now - timedelta(seconds=seconds + 10),
        submitted_at=now,
        graded_at=now,
        duration_seconds=seconds,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def test_sweep_finalizes_a_quest_past_closes_at(session):
    from app.workers.main import _sweep_expired_quests

    owner = await _user(session, "auto_owner@q.com", "teacher")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    quest = await QuestService(session).create(
        owner,
        [{"rank": 1, "reward_amount": 50}],
        title="Auto Finalize Quest",
        top_n_winners=1,
        status="open",
    )
    student = await _user(session, "auto_student@q.com")
    attempt = await _graded_attempt(session, exam, student, 9000, 30)
    # Record the attempt while the quest window is still open (no closes_at
    # yet), then simulate time passing by setting closes_at to the past —
    # mirrors a real quest whose deadline elapses after students attempted.
    await QuestService(session).record_attempt(quest.id, student, exam_attempt_id=attempt.id)
    quest.closes_at = datetime.now(UTC) - timedelta(minutes=5)
    await session.commit()

    finalized = await _sweep_expired_quests()
    # Scoped to THIS quest: the sweep may also finalize expired quests left over
    # by sibling tests in the shared session DB, so assert >= 1, not == 1.
    assert finalized >= 1

    await session.close()
    from sqlalchemy.ext.asyncio import async_sessionmaker

    # Re-read through a fresh session bound to the same engine as `session`.
    sm = async_sessionmaker(session.bind, expire_on_commit=False)
    async with sm() as fresh:
        from app.models.quest import Quest

        refreshed = await fresh.get(Quest, quest.id)
        assert refreshed.status == "finalized"
        winners = (
            await fresh.execute(select(QuestWinner).where(QuestWinner.quest_id == quest.id))
        ).scalars().all()
        assert len(winners) == 1
        assert winners[0].user_id == student.id

        ledger = (
            await fresh.execute(
                select(WalletLedgerEntry)
                .join(WalletAccount, WalletAccount.id == WalletLedgerEntry.account_id)
                .where(WalletAccount.user_id == student.id)
            )
        ).scalars().all()
        assert len(ledger) == 1
        assert ledger[0].amount == 50

        notif = (
            await fresh.execute(select(Notification).where(Notification.user_id == student.id))
        ).scalars().all()
        assert any(n.kind == "reward" for n in notif)


async def test_sweep_is_idempotent_on_a_second_pass(session):
    from app.workers.main import _sweep_expired_quests

    owner = await _user(session, "auto_owner2@q.com", "teacher")
    exam = Exam(title="E2", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    quest = await QuestService(session).create(
        owner,
        [{"rank": 1, "reward_amount": 30}],
        title="Auto Finalize Quest 2",
        top_n_winners=1,
        status="open",
    )
    student = await _user(session, "auto_student2@q.com")
    attempt = await _graded_attempt(session, exam, student, 8000, 15)
    await QuestService(session).record_attempt(quest.id, student, exam_attempt_id=attempt.id)
    quest.closes_at = datetime.now(UTC) - timedelta(minutes=5)
    await session.commit()

    first_pass = await _sweep_expired_quests()
    # >= 1: sibling tests may leave their own expired quests in the shared DB.
    assert first_pass >= 1
    # The quest created here is now finalized -> it is no longer returned by
    # list_expired_open. Re-running must not re-finalize *this* quest.
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.quest import Quest

    sm = async_sessionmaker(session.bind, expire_on_commit=False)
    async with sm() as fresh:
        refreshed = await fresh.get(Quest, quest.id)
        assert refreshed.status == "finalized"
    second_pass = await _sweep_expired_quests()
    async with sm() as fresh:
        again = await fresh.get(Quest, quest.id)
        assert again.status == "finalized"
    # second_pass may finalize other expired quests; must never touch ours again.
    assert second_pass >= 0

    async with sm() as fresh:
        ledger = (
            await fresh.execute(
                select(WalletLedgerEntry)
                .join(WalletAccount, WalletAccount.id == WalletLedgerEntry.account_id)
                .where(WalletAccount.user_id == student.id)
            )
        ).scalars().all()
        # Still exactly one ledger entry — no duplicate allocation.
        assert len(ledger) == 1


async def test_sweep_ignores_quests_without_closes_at_or_still_open(session):
    from app.models.quest import Quest
    from app.workers.main import _sweep_expired_quests

    owner = await _user(session, "auto_owner3@q.com", "teacher")
    no_deadline = await QuestService(session).create(
        owner,
        [{"rank": 1, "reward_amount": 10}],
        title="No deadline",
        top_n_winners=1,
        status="open",
        closes_at=None,
    )
    future = await QuestService(session).create(
        owner,
        [{"rank": 1, "reward_amount": 10}],
        title="Future deadline",
        top_n_winners=1,
        status="open",
        closes_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await session.commit()

    await _sweep_expired_quests()
    # These two quests must remain open regardless of what sibling tests left
    # behind (the sweep count is global, so assert on our quests' state).
    for quest_id in (no_deadline.id, future.id):
        refreshed = await session.get(Quest, quest_id)
        assert refreshed.status == "open"
