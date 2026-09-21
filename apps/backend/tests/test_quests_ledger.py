"""Quest winner determinism, reward idempotency and the double-entry ledger.

These are the highest-risk correctness properties in QLoot.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Exam, ExamAttempt, User
from app.services.keys import reward_key
from app.services.quest_service import QuestService
from app.services.reward_engine import RewardEngine

pytestmark = pytest.mark.integration


async def _user(session, email, role="student") -> User:
    from sqlalchemy import select
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
    # Re-load with roles eager-loaded so has_role() never lazy-loads.
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == u.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def _graded_attempt(session, exam, user, score_bp, seconds, offset=0):
    now = datetime.now(UTC)
    attempt = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        attempt_number=1,
        status="graded",
        score_bp=score_bp,
        passed=score_bp >= 6000,
        started_at=now - timedelta(seconds=seconds + 10),
        submitted_at=now + timedelta(seconds=offset),
        graded_at=now,
        duration_seconds=seconds,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def _make_quest(session, owner, top_n=3, ranks=(100, 60, 40)):
    return await QuestService(session).create(
        owner,
        [{"rank": i + 1, "reward_amount": a} for i, a in enumerate(ranks)],
        title="Speed Quest",
        top_n_winners=top_n,
        status="open",
    )


async def test_winners_are_deterministic_and_fastest_valid(session):
    owner = await _user(session, "owner@q.com", "teacher")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    # Three valid students with different scores; a fourth below passing.
    students = [await _user(session, f"s{i}@q.com") for i in range(4)]
    scores = [9000, 9000, 7000, 4000]  # 4th fails passing (min 6000)
    durations = [100, 50, 200, 10]

    quest = await _make_quest(session, owner)
    for s, sc, d in zip(students, scores, durations, strict=False):
        attempt = await _graded_attempt(session, exam, s, sc, d)
        await QuestService(session).record_attempt(quest.id, s, exam_attempt_id=attempt.id)
    await session.flush()

    _, winners = await QuestService(session).finalize(quest.id, owner)
    assert len(winners) == 3
    # Rank 1: highest score, then fastest. Two 9000s -> faster (50s) is rank 1.
    assert winners[0].score_bp == 9000
    assert winners[1].score_bp == 9000
    assert winners[0].duration_seconds < winners[1].duration_seconds
    # Rank 3: 7000
    assert winners[2].score_bp == 7000
    # The 4000 student never appears.
    assert all(w.user_id != students[3].id for w in winners)
    # Ranks are 1,2,3
    assert [w.rank for w in winners] == [1, 2, 3]


async def test_finalize_is_idempotent(session):
    owner = await _user(session, "owner2@q.com", "teacher")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()
    quest = await _make_quest(session, owner)
    students = [await _user(session, f"t{i}@q.com") for i in range(3)]
    for s, sc, d in zip(students, [8000, 8000, 8000], [10, 20, 30], strict=False):
        attempt = await _graded_attempt(session, exam, s, sc, d)
        await QuestService(session).record_attempt(quest.id, s, exam_attempt_id=attempt.id)
    await session.flush()

    svc = QuestService(session)
    _, w1 = await svc.finalize(quest.id, owner)
    _, w2 = await svc.finalize(quest.id, owner)
    assert len(w1) == 3
    assert len(w2) == 3
    # Deterministic: same winners, same ranks.
    assert sorted(w.rank for w in w1) == sorted(w.rank for w in w2)
    assert {w.user_id for w in w1} == {w.user_id for w in w2}


async def test_reward_key_matches_expected_formula():
    q = uuid.uuid4()
    u = uuid.uuid4()
    k1 = reward_key(q, u, 1, 1)
    k2 = reward_key(q, u, 1, 1)
    k3 = reward_key(q, u, 2, 1)
    assert k1 == k2
    assert k1 != k3
    assert k1.startswith("0x") and len(k1) == 66


async def test_reward_credit_is_idempotent(session):
    owner = await _user(session, "owner3@q.com", "teacher")
    student = await _user(session, "earner@q.com")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()
    quest = await _make_quest(session, owner)

    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    # Re-allocate same rank: must return the same allocation, no second credit.
    alloc2 = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    assert alloc.id == alloc2.id

    balance = await engine.balance(student.id)
    assert balance == 100

    cached, computed = await engine.reconcile(student.id)
    assert cached == computed == 100


async def test_ledger_never_double_credits_same_reference(session):
    student = await _user(session, "dup@q.com")
    engine = RewardEngine(session)
    e1 = await engine.credit(
        user=student,
        amount=50,
        reference_type="test",
        reference_id="ref-1",
        reward_key_value="rk-1",
        token_id=0,
    )
    e2 = await engine.credit(
        user=student,
        amount=50,
        reference_type="test",
        reference_id="ref-1",
        reward_key_value="rk-1",
        token_id=0,
    )
    assert e1.id == e2.id
    assert await engine.balance(student.id) == 50


async def test_withdrawal_debit_and_insufficient_funds(session):
    student = await _user(session, "wd@q.com")
    engine = RewardEngine(session)
    await engine.credit(
        user=student,
        amount=80,
        reference_type="test",
        reference_id="r",
        reward_key_value="rk",
        token_id=0,
    )
    wd_id = uuid.uuid4()
    await engine.debit_for_withdrawal(
        user=student, amount=30, withdrawal_id=wd_id, destination="0x" + "1" * 40
    )
    assert await engine.balance(student.id) == 50

    from app.core.errors import ConflictError

    with pytest.raises(ConflictError):
        await engine.debit_for_withdrawal(
            user=student, amount=999, withdrawal_id=uuid.uuid4(), destination="0x" + "1" * 40
        )


async def test_reward_outbox_created_transactionally(session):
    """Every reward must produce exactly one outbox row (no lost events)."""
    from sqlalchemy import func, select

    from app.models.wallet import TransactionOutbox

    owner = await _user(session, "ob@q.com", "teacher")
    student = await _user(session, "obe@q.com")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()
    quest = await _make_quest(session, owner)
    engine = RewardEngine(session)
    await engine.allocate_quest_reward(quest=quest, user=student, rank=1, amount=100, score_bp=9000)
    count = (
        await session.execute(
            select(func.count())
            .select_from(TransactionOutbox)
            .where(TransactionOutbox.topic == "reward")
        )
    ).scalar_one()
    assert count == 1


async def test_transaction_rollback_leaves_no_partial_state(engine):
    """A failed operation must not persist partial writes."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.errors import ConflictError
    from app.models.wallet import RewardAllocation

    student_holder = {}
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        student = await _user(s, "rb@q.com")
        student_holder["id"] = student.id
        await s.commit()

    async with sm() as s:
        student = await s.get(User, student_holder["id"])
        engine_ = RewardEngine(s)
        try:
            # Negative amount raises before any write.
            await engine_.credit(
                user=student,
                amount=-5,
                reference_type="test",
                reference_id="rb",
                reward_key_value="rb",
                token_id=0,
            )
        except ConflictError:
            await s.rollback()
    async with sm() as s:
        from sqlalchemy import func, select

        n = (await s.execute(select(func.count()).select_from(RewardAllocation))).scalar_one()
        # No allocation rows from the failed op.
        assert n == 0


async def test_late_submission_is_marked_invalid_and_cannot_win(session):
    """A submission after closes_at must be recorded but never win."""
    owner = await _user(session, "owner_late@q.com", "teacher")
    student = await _user(session, "late@q.com")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    # Quest that already closed an hour ago.
    closed = await QuestService(session).create(
        owner,
        [{"rank": 1, "reward_amount": 100}],
        title="Closed Quest",
        top_n_winners=1,
        status="open",
        opens_at=datetime.now(UTC) - timedelta(days=2),
        closes_at=datetime.now(UTC) - timedelta(hours=1),
    )
    attempt = await _graded_attempt(session, exam, student, 9500, 30)
    qa = await QuestService(session).record_attempt(closed.id, student, exam_attempt_id=attempt.id)
    assert qa.is_valid is False
    assert qa.invalid_reason and "closed" in qa.invalid_reason

    _, winners = await QuestService(session).finalize(closed.id, owner)
    assert winners == []


async def test_attempt_before_open_is_invalid(session):
    owner = await _user(session, "owner_future@q.com", "teacher")
    student = await _user(session, "early@q.com")
    exam = Exam(title="E", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()
    future = await QuestService(session).create(
        owner,
        [{"rank": 1, "reward_amount": 100}],
        title="Future Quest",
        top_n_winners=1,
        status="open",
        opens_at=datetime.now(UTC) + timedelta(days=1),
    )
    attempt = await _graded_attempt(session, exam, student, 9500, 30)
    qa = await QuestService(session).record_attempt(future.id, student, exam_attempt_id=attempt.id)
    assert qa.is_valid is False
    assert qa.invalid_reason and "before" in qa.invalid_reason


async def test_refund_reward_preserves_ledger_invariant(session):
    """Refunding a spent reward must not silently floor the balance at 0.

    The double-entry invariant ``credit - debit == cached_balance`` (which
    ``reconcile()`` checks) must hold even when the credit was already spent.
    """
    student = await _user(session, "refund@q.com")
    engine = RewardEngine(session)
    alloc_id = uuid.uuid4()
    await engine.credit(
        user=student,
        amount=100,
        reference_type="reward",
        reference_id=str(alloc_id),
        reward_key_value="rk",
        token_id=0,
    )
    # Spend it: withdraw the whole balance so nothing remains.
    await engine.debit_for_withdrawal(
        user=student, amount=100, withdrawal_id=uuid.uuid4(), destination="0x" + "2" * 40
    )
    assert await engine.balance(student.id) == 0

    # Now the on-chain mint fails -> refund the original reward.
    await engine.refund_reward(user_id=student.id, amount=100, allocation_id=alloc_id)

    cached, computed = await engine.reconcile(student.id)
    assert cached == computed, "refund must keep cached balance reconcilable"
    assert cached == -100
