"""On-chain worker logic (used by the blockchain worker process and admin
retry endpoints).

Given a transaction_outbox row, this builds a BlockchainTransaction record,
signs+sends (or dry-runs), and records the resulting hash. Indexer later
confirms it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.blockchain.client import get_chain_client
from app.core.config import settings
from app.core.errors import ChainError
from app.core.logging import get_logger
from app.models.wallet import (
    BlockchainTransaction,
    RewardAllocation,
    WithdrawalRequest,
)

log = get_logger("chain_worker")


async def _existing_tx(session: AsyncSession, key: str) -> BlockchainTransaction | None:
    return (
        await session.execute(
            select(BlockchainTransaction).where(BlockchainTransaction.idempotency_key == key)
        )
    ).scalar_one_or_none()


async def process_outbox_item(session: AsyncSession, outbox_id: uuid.UUID) -> bool:
    from app.models.wallet import TransactionOutbox

    item = await session.get(TransactionOutbox, outbox_id)
    if item is None or item.status in ("done", "failed"):
        return False

    client = get_chain_client()
    tx = await _existing_tx(session, item.idempotency_key)
    if tx is None:
        tx = BlockchainTransaction(
            idempotency_key=item.idempotency_key,
            network=settings.blockchain_network,
            chain_id=settings.chain_id,
            from_address=settings.treasury_address or "0x" + "0" * 40,
            contract_address=settings.opc_contract_address or None,
            method=item.topic,
            arguments=item.payload,
            status="queued",
        )
        session.add(tx)
        await session.flush()

    try:
        if item.topic == "reward":
            payload = item.payload or {}
            receipt = await client.record_reward(
                reward_key=payload["reward_key"],
                quest_ref=payload.get("quest_ref") or "0x" + "0" * 64,
                user_ref=payload["user_ref"],
                rank=int(payload.get("rank", 0)),
                amount=int(payload["amount"]),
                token_id=int(payload.get("token_id", 0)),
            )
            tx.method = "recordReward"
            if payload.get("allocation_id"):
                allocation = await session.get(
                    RewardAllocation, uuid.UUID(payload["allocation_id"])
                )
                if allocation is not None:
                    allocation.blockchain_transaction_id = tx.id
        elif item.topic == "withdrawal":
            payload = item.payload or {}
            receipt = await client.complete_withdrawal(
                withdrawal_ref=payload.get("withdrawal_id", tx.idempotency_key),
                destination=payload["destination"],
                amount=int(payload["amount"]),
                token_id=int(payload.get("token_id", 0)),
            )
            tx.method = "completeWithdrawal"
            if payload.get("withdrawal_id"):
                wd = await session.get(WithdrawalRequest, uuid.UUID(payload["withdrawal_id"]))
                if wd is not None:
                    wd.blockchain_transaction_id = tx.id
                    wd.status = "submitted"
        else:
            raise ChainError(f"Unknown outbox topic: {item.topic}")

        tx.transaction_hash = receipt.tx_hash
        tx.block_number = receipt.block_number
        tx.gas_used = receipt.gas_used
        tx.submitted_at = datetime.now(UTC)
        tx.status = "submitted" if not receipt.dry_run else "pending"
        tx.error_code = None
        tx.error_message = None
        item.status = "done"
        item.processed_at = datetime.now(UTC)
        await session.flush()
        from app.core import metrics

        metrics.incr("blockchain_transactions_total", method=tx.method)
        log.info("outbox_processed", topic=item.topic, tx_hash=receipt.tx_hash)
        return True
    except ChainError as exc:
        item.attempts += 1
        item.last_error = str(exc)
        tx.status = "failed"
        tx.error_code = "chain_error"
        tx.error_message = str(exc)
        from app.core import metrics

        metrics.incr("blockchain_failed_transactions_total", topic=item.topic)
        if item.attempts >= item.max_attempts:
            item.status = "failed"
            payload = item.payload or {}
            allocation_id = payload.get("allocation_id")
            if item.topic == "reward" and allocation_id:
                allocation = await session.get(RewardAllocation, uuid.UUID(allocation_id))
                if allocation is not None:
                    allocation.status = "failed"
                    allocation.error_message = str(exc)
        await session.flush()
        log.warning("outbox_failed", topic=item.topic, error=str(exc))
        return False


async def refresh_confirmations(session: AsyncSession, limit: int = 50) -> int:
    """Indexer helper: update confirmation counts + confirm/complete rows."""
    client = get_chain_client()
    stmt = (
        select(BlockchainTransaction)
        .where(BlockchainTransaction.status.in_(("submitted", "pending")))
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    updated = 0
    for tx in rows:
        if not tx.transaction_hash:
            continue
        confirmations = client.get_confirmations(tx.transaction_hash)
        tx.confirmation_count = confirmations
        tx.last_checked_at = datetime.now(UTC)
        if confirmations >= settings.opc_confirmations:
            receipt = client.get_receipt(tx.transaction_hash)
            if receipt is not None and receipt.status == 1:
                tx.status = "confirmed"
                tx.confirmed_at = datetime.now(UTC)
                if receipt.block_number is not None:
                    tx.block_number = receipt.block_number
                await _mark_confirmed(session, tx)
            elif receipt is not None and receipt.status == 0:
                tx.status = "failed"
                tx.error_code = "reverted"
                tx.error_message = "Transaction reverted"
        updated += 1
    await session.flush()
    return updated


async def _mark_confirmed(session: AsyncSession, tx: BlockchainTransaction) -> None:
    args = tx.arguments or {}
    if tx.method == "recordReward" and args.get("allocation_id"):
        allocation = await session.get(RewardAllocation, uuid.UUID(args["allocation_id"]))
        if allocation is not None:
            allocation.status = "confirmed"
            allocation.confirmed_at = datetime.now(UTC)
    if tx.method == "completeWithdrawal" and args.get("withdrawal_id"):
        wd = await session.get(WithdrawalRequest, uuid.UUID(args["withdrawal_id"]))
        if wd is not None:
            wd.status = "completed"
