"""Blockchain worker: outbox -> tx submission -> confirmation (dry-run)."""

from __future__ import annotations

import uuid

import pytest

from app.blockchain.worker_logic import process_outbox_item, refresh_confirmations
from app.models import Quest, User
from app.models.wallet import BlockchainTransaction, RewardAllocation, TransactionOutbox
from app.services.reward_engine import RewardEngine

pytestmark = pytest.mark.integration


async def _outbox_for_allocation(session, allocation_id) -> TransactionOutbox | None:
    """Return the outbox row whose payload references a given allocation.

    Tests share a session-scoped database, so selecting the global `.first()`
    outbox row is unsafe: an earlier test may have left reward rows behind.
    """
    from sqlalchemy import select

    rows = (await session.execute(select(TransactionOutbox))).scalars().all()
    target = str(allocation_id)
    for row in rows:
        payload = row.payload or {}
        if payload.get("allocation_id") == target:
            return row
    return None


async def _tx_for_outbox(session, idempotency_key) -> BlockchainTransaction | None:
    """The BlockchainTransaction created for a given outbox idempotency key."""
    from sqlalchemy import select

    return (
        await session.execute(
            select(BlockchainTransaction).where(
                BlockchainTransaction.idempotency_key == idempotency_key
            )
        )
    ).scalar_one_or_none()


async def _mk_user(session, email):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models.identity import Role, UserRole

    role = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    u = User(
        email=email,
        full_name="T",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:64],
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role.id))
    await session.flush()
    return (
        await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == u.id)
        )
    ).scalar_one()


async def test_outbox_processed_into_transaction(session):
    owner = await _mk_user(session, "bo@q.com")
    student = await _mk_user(session, "bs@q.com")
    quest = Quest(title="Q", owner_id=owner.id, status="open", top_n_winners=3)
    session.add(quest)
    await session.flush()

    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    # Select THIS allocation's outbox row (earlier tests may leave rows behind
    # in the session-scoped DB, so a global `.first()` is not safe).
    item = await _outbox_for_allocation(session, alloc.id)
    assert item is not None

    ok = await process_outbox_item(session, item.id)
    assert ok is True

    tx = await _tx_for_outbox(session, item.idempotency_key)
    assert tx is not None
    assert tx.transaction_hash is not None
    assert tx.method == "rewardUser"
    assert tx.idempotency_key

    refreshed_alloc = await session.get(RewardAllocation, alloc.id)
    assert refreshed_alloc.blockchain_transaction_id == tx.id


async def test_outbox_processing_is_idempotent(session):
    owner = await _mk_user(session, "bo2@q.com")
    student = await _mk_user(session, "bs2@q.com")
    quest = Quest(title="Q2", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()
    engine = RewardEngine(session)
    await engine.allocate_quest_reward(quest=quest, user=student, rank=1, amount=100, score_bp=9000)

    from sqlalchemy import select

    item = (await session.execute(select(TransactionOutbox))).scalars().first()
    assert await process_outbox_item(session, item.id) is True
    # Second call: item is done -> no-op.
    assert await process_outbox_item(session, item.id) is False

    txs = (await session.execute(select(BlockchainTransaction))).scalars().all()
    assert len(txs) == 1  # exactly one tx, no duplicate


async def test_confirmations_promote_reward_to_confirmed(session):
    owner = await _mk_user(session, "bo3@q.com")
    student = await _mk_user(session, "bs3@q.com")
    quest = Quest(title="Q3", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()
    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    item = await _outbox_for_allocation(session, alloc.id)
    await process_outbox_item(session, item.id)

    n = await refresh_confirmations(session)
    assert n >= 1
    refreshed = await session.get(RewardAllocation, alloc.id)
    assert refreshed.status == "confirmed"


async def test_reward_allocation_unique_per_quest_user_type(session):
    owner = await _mk_user(session, "bo4@q.com")
    student = await _mk_user(session, "bs4@q.com")
    quest = Quest(title="Q4", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()
    engine = RewardEngine(session)
    await engine.allocate_quest_reward(quest=quest, user=student, rank=1, amount=100, score_bp=9000)
    # Same quest+user+type must not double-pay even with a different rank/reward key.
    await engine.allocate_quest_reward(quest=quest, user=student, rank=2, amount=60, score_bp=9000)
    from sqlalchemy import func, select

    # Count only THIS quest's allocations (the DB is shared across tests).
    total = (
        await session.execute(
            select(func.count())
            .select_from(RewardAllocation)
            .where(RewardAllocation.quest_id == quest.id)
        )
    ).scalar_one()
    assert total == 1


async def test_confirmation_records_blockchain_event(session):
    """Indexing a confirmed tx must persist an event row (non-empty feed)."""
    from sqlalchemy import select

    from app.models.wallet import BlockchainEvent

    owner = await _mk_user(session, "bo5@q.com")
    student = await _mk_user(session, "bs5@q.com")
    quest = Quest(title="Q5", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()
    await RewardEngine(session).allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    item = (await session.execute(select(TransactionOutbox))).scalars().first()
    await process_outbox_item(session, item.id)
    await refresh_confirmations(session)

    events = (await session.execute(select(BlockchainEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].event_name == "rewardUserConfirmed"


async def test_reward_refund_reverses_credit(session):
    student = await _mk_user(session, "refund@q.com")
    engine = RewardEngine(session)
    await engine.credit(
        user=student,
        amount=100,
        reference_type="reward",
        reference_id="alloc-1",
        reward_key_value="rk-1",
        token_id=0,
    )
    assert await engine.balance(student.id) == 100
    alloc_id = uuid.uuid4()
    await engine.refund_reward(user_id=student.id, amount=100, allocation_id=alloc_id)
    assert await engine.balance(student.id) == 0
    cached, computed = await engine.reconcile(student.id)
    assert cached == computed == 0
    # Idempotent: a second refund must not double-debit.
    await engine.refund_reward(user_id=student.id, amount=100, allocation_id=alloc_id)
    assert await engine.balance(student.id) == 0


async def test_withdrawal_refund_restores_balance(session):
    student = await _mk_user(session, "wdref@q.com")
    engine = RewardEngine(session)
    await engine.credit(
        user=student,
        amount=80,
        reference_type="reward",
        reference_id="r1",
        reward_key_value="rk1",
        token_id=0,
    )
    wd_id = uuid.uuid4()
    await engine.debit_for_withdrawal(
        user=student, amount=50, withdrawal_id=wd_id, destination="0x" + "1" * 40
    )
    assert await engine.balance(student.id) == 30
    # A failed payout returns the funds.
    await engine.refund_withdrawal(user_id=student.id, amount=50, withdrawal_id=wd_id)
    assert await engine.balance(student.id) == 80


async def _mk_outbox(session, topic, payload, key):
    item = TransactionOutbox(topic=topic, idempotency_key=key, payload=payload, status="pending")
    session.add(item)
    await session.flush()
    return item


async def test_airdrop_topic_mints(session):
    """An 'airdrop' outbox item mints the asset (dry-run: deterministic hash)."""
    from sqlalchemy import select

    item = await _mk_outbox(
        session,
        "airdrop",
        {"to": "0x" + "ab" * 20, "amount": 500, "asset": "QTC"},
        "airdrop-1",
    )
    assert await process_outbox_item(session, item.id) is True
    tx = (await session.execute(select(BlockchainTransaction))).scalars().first()
    assert tx.method == "mint"
    assert tx.transaction_hash is not None


async def test_swap_topic_routes_through_orx(session):
    from sqlalchemy import select

    item = await _mk_outbox(session, "swap", {"asset": "ORT", "amount": 10}, "swap-1")
    assert await process_outbox_item(session, item.id) is True
    tx = (await session.execute(select(BlockchainTransaction))).scalars().first()
    assert tx.method == "swapOptFor"


async def test_ai_request_topic_pays_with_ort(session):
    from sqlalchemy import select

    item = await _mk_outbox(session, "ai_request", {"requests": 3}, "ai-1")
    assert await process_outbox_item(session, item.id) is True
    tx = (await session.execute(select(BlockchainTransaction))).scalars().first()
    assert tx.method == "payAiRequest"


async def test_pause_topic_calls_contract(session):
    from sqlalchemy import select

    item = await _mk_outbox(session, "pause", {"asset": "OPT"}, "pause-1")
    assert await process_outbox_item(session, item.id) is True
    tx = (await session.execute(select(BlockchainTransaction))).scalars().first()
    assert tx.method == "pause"


async def test_withdrawal_topic_burns_and_confirms(session):
    """A withdrawal outbox item burns on-chain and completes on confirmation."""
    from sqlalchemy import select

    from app.models.wallet import WithdrawalRequest

    student = await _mk_user(session, "wdflow@q.com")
    wd = WithdrawalRequest(
        user_id=student.id,
        reward_key="wd-0",
        destination_address="0x" + "9" * 40,
        token_id=0,
        amount=10,
        status="requested",
    )
    session.add(wd)
    await session.flush()
    item = await _mk_outbox(
        session,
        "withdrawal",
        {"withdrawal_id": str(wd.id), "amount": 10, "asset": "OPT"},
        "wdflow-1",
    )
    assert await process_outbox_item(session, item.id) is True
    tx = (await session.execute(select(BlockchainTransaction))).scalars().first()
    assert tx.method == "burn"
    # The withdrawal is linked to the tx now.
    assert (await session.get(WithdrawalRequest, wd.id)).status == "submitted"

    # Indexing confirms it and completes the withdrawal.
    await refresh_confirmations(session)
    assert (await session.get(WithdrawalRequest, wd.id)).status == "completed"


async def test_unknown_topic_is_rejected_retryably(session):
    item = await _mk_outbox(session, "nonsense", {}, "bad-1")
    assert await process_outbox_item(session, item.id) is False
