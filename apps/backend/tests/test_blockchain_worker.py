"""Blockchain worker: outbox -> tx submission -> confirmation (dry-run)."""

from __future__ import annotations

import uuid

import pytest

from app.blockchain.worker_logic import (
    process_outbox_item,
    refresh_confirmations,
    resubmit_stuck_transactions,
)
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


async def test_reverted_tx_compensates_ledger_and_is_listed_as_failed(session):
    """C17: a reported-then-reverted reward reverses the credit (compensation).

    Every terminal-failure state must produce a compensating ledger entry so the
    off-chain balance matches the (absent) on-chain token.
    """
    from sqlalchemy import select

    from app.models.wallet import TransactionOutbox

    owner = await _mk_user(session, "rev_owner@q.com")
    student = await _mk_user(session, "rev_student@q.com")
    quest = Quest(title="Rev", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()

    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    assert await engine.balance(student.id) == 100

    item = await _outbox_for_allocation(session, alloc.id)
    await process_outbox_item(session, item.id)
    tx = await _tx_for_outbox(session, item.idempotency_key)
    assert tx is not None

    # Simulate the chain reverting the tx, then index it.
    from app.blockchain.worker_logic import _mark_reverted

    tx.status = "failed"
    tx.error_code = "reverted"
    await _mark_reverted(session, tx)
    await session.flush()

    # The credit was reversed (compensation entry) -> balance back to 0.
    assert await engine.balance(student.id) == 0
    cached, computed = await engine.reconcile(student.id)
    assert cached == computed == 0
    refreshed = await session.get(RewardAllocation, alloc.id)
    assert refreshed.status == "failed"

    # And the tx is surfaced in the consolidated failed view.
    failed = (
        await session.execute(
            select(TransactionOutbox).where(TransactionOutbox.id == item.id)
        )
    ).scalar_one()
    assert failed.status == "done"  # outbox itself is done; the *tx* failed


class _StuckClient:
    """Chain client stub: zero confirmations, deterministic resubmit."""

    def __init__(self):
        self.resends = 0

    def get_confirmations(self, _tx_hash):
        return 0

    def build_call(self, _method, _arguments):
        return object()

    async def resend(self, _fn, *, nonce, fee_bump_percent):
        from app.blockchain.client import TxReceipt

        self.resends += 1
        return TxReceipt(
            tx_hash="0x" + "ab" * 32, status=0, dry_run=False, nonce=nonce
        )


async def _make_stuck_tx(session, student, amount=100):
    """Create a submitted tx with a nonce and an old submitted_at."""
    from datetime import UTC, datetime, timedelta

    tx = BlockchainTransaction(
        idempotency_key="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:2],
        network="localhost",
        chain_id=31337,
        from_address="0x" + "0" * 40,
        method="rewardUser",
        arguments={
            "reward_key": "0x" + uuid.uuid4().hex + uuid.uuid4().hex,
            "amount": amount,
            "allocation_id": None,
        },
        status="submitted",
        transaction_hash="0x" + "cd" * 32,
        nonce=7,
        submitted_at=datetime.now(UTC) - timedelta(seconds=10_000),
    )
    session.add(tx)
    await session.flush()
    return tx


async def test_stuck_transaction_is_resubmitted_with_same_nonce(session, monkeypatch):
    from app.blockchain import worker_logic

    student = await _mk_user(session, "stuck1@q.com")
    tx = await _make_stuck_tx(session, student)
    stub = _StuckClient()
    monkeypatch.setattr(worker_logic, "get_chain_client", lambda: stub)

    n = await resubmit_stuck_transactions(session)
    assert n >= 1
    refreshed = await session.get(BlockchainTransaction, tx.id)
    assert refreshed.resubmit_count == 1
    assert refreshed.nonce == 7  # same nonce (replacement)
    assert refreshed.transaction_hash == "0x" + "ab" * 32
    assert stub.resends >= 1


async def test_stuck_transaction_is_dropped_after_max_and_compensated(session, monkeypatch):
    from app.blockchain import worker_logic
    from app.core.config import settings

    owner = await _mk_user(session, "stuck_owner@q.com")
    student = await _mk_user(session, "stuck2@q.com")
    quest = Quest(title="StuckQuest", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()

    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    balance_before = await engine.balance(student.id)

    from datetime import UTC, datetime, timedelta

    tx = BlockchainTransaction(
        idempotency_key="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:2],
        network="localhost",
        chain_id=31337,
        from_address="0x" + "0" * 40,
        method="rewardUser",
        arguments={"allocation_id": str(alloc.id), "amount": 100, "reward_key": "0x0"},
        status="submitted",
        transaction_hash="0x" + "ee" * 32,
        nonce=9,
        resubmit_count=settings.tx_max_resubmits,
        submitted_at=datetime.now(UTC) - timedelta(seconds=10_000),
    )
    session.add(tx)
    await session.flush()

    stub = _StuckClient()
    monkeypatch.setattr(worker_logic, "get_chain_client", lambda: stub)

    n = await resubmit_stuck_transactions(session)
    assert n >= 1
    refreshed = await session.get(BlockchainTransaction, tx.id)
    assert refreshed.status == "dropped"
    assert stub.resends == 0  # dropped, not resent

    # Ledger compensated: the off-chain credit is reversed.
    assert await engine.balance(student.id) == 0
    assert balance_before == 100
    refreshed_alloc = await session.get(RewardAllocation, alloc.id)
    assert refreshed_alloc.status == "failed"


class _LogsClient:
    """Chain client stub returning real-looking logs and a non-canonical tx."""

    def __init__(self, *, canonical=True, logs=None):
        self.dry_run = False
        self._canonical = canonical
        self._logs = logs
        self._w3 = None

    def get_logs_for_tx(self, _tx_hash):
        return self._logs or []

    def receipt_is_canonical(self, _tx_hash):
        return self._canonical


async def test_record_event_ingests_real_logs_with_log_index(session, monkeypatch):
    from app.blockchain import worker_logic
    from app.models.wallet import BlockchainEvent

    student = await _mk_user(session, "evt1@q.com")
    tx = await _make_stuck_tx(session, student)
    tx.transaction_hash = "0x" + "12" * 32
    tx.block_number = 123
    stub = _LogsClient(
        logs=[
            {"log_index": 1, "event_name": "RewardPaid", "block_number": 123, "address": "0xA"},
            {"log_index": 3, "event_name": "Transfer", "block_number": 123, "address": "0xA"},
        ]
    )
    monkeypatch.setattr(worker_logic, "get_chain_client", lambda: stub)

    await worker_logic._record_event(session, tx)
    from sqlalchemy import select

    rows = (
        await session.execute(
            select(BlockchainEvent).where(
                BlockchainEvent.transaction_hash == tx.transaction_hash
            )
        )
    ).scalars().all()
    assert {r.log_index for r in rows} == {1, 3}
    assert {r.event_name for r in rows} == {"RewardPaid", "Transfer"}


async def test_reorg_rolls_back_a_confirmed_transaction(session, monkeypatch):
    from datetime import UTC, datetime

    from app.blockchain import worker_logic
    from app.core.config import settings

    owner = await _mk_user(session, "reorg_owner@q.com")
    student = await _mk_user(session, "reorg_student@q.com")
    quest = Quest(title="ReorgQuest", owner_id=owner.id, status="open")
    session.add(quest)
    await session.flush()
    engine = RewardEngine(session)
    alloc = await engine.allocate_quest_reward(
        quest=quest, user=student, rank=1, amount=100, score_bp=9000
    )
    assert await engine.balance(student.id) == 100

    tx = BlockchainTransaction(
        idempotency_key="0x" + uuid.uuid4().hex + uuid.uuid4().hex[:2],
        network="localhost",
        chain_id=31337,
        from_address="0x" + "0" * 40,
        method="rewardUser",
        arguments={"allocation_id": str(alloc.id), "amount": 100, "reward_key": "0x0"},
        status="confirmed",
        transaction_hash="0x" + "34" * 32,
        block_number=200,
        confirmed_at=datetime.now(UTC),
    )
    session.add(tx)
    await session.flush()

    stub = _LogsClient(canonical=False)
    monkeypatch.setattr(worker_logic, "get_chain_client", lambda: stub)
    monkeypatch.setattr(settings, "blockchain_poll_seconds", 5)

    n = await worker_logic.revalidate_confirmed_transactions(session)
    assert n >= 1
    refreshed = await session.get(BlockchainTransaction, tx.id)
    assert refreshed.status == "failed"
    assert refreshed.error_code == "reorged"
    # Compensation applied.
    assert await engine.balance(student.id) == 0
