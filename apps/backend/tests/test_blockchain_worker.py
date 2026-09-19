"""Blockchain worker: outbox -> tx submission -> confirmation (dry-run)."""

from __future__ import annotations

import uuid

import pytest

from app.blockchain.worker_logic import process_outbox_item, refresh_confirmations
from app.models import Quest, User
from app.models.wallet import BlockchainTransaction, RewardAllocation, TransactionOutbox
from app.services.reward_engine import RewardEngine

pytestmark = pytest.mark.integration


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
    outbox = (await session.execute(TransactionOutbox.__table__.select())).first()
    assert outbox is not None

    item = (
        (await session.execute(__import__("sqlalchemy").select(TransactionOutbox)))
        .scalars()
        .first()
    )
    ok = await process_outbox_item(session, item.id)
    assert ok is True

    tx = (
        (await session.execute(__import__("sqlalchemy").select(BlockchainTransaction)))
        .scalars()
        .first()
    )
    assert tx is not None
    assert tx.transaction_hash is not None
    assert tx.method == "recordReward"
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
    from sqlalchemy import select

    owner = await _mk_user(session, "bo3@q.com")
    student = await _mk_user(session, "bs3@q.com")
    quest = Quest(title="Q3", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()
    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    item = (await session.execute(select(TransactionOutbox))).scalars().first()
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

    total = (await session.execute(select(func.count()).select_from(RewardAllocation))).scalar_one()
    assert total == 1
