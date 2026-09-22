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


def _require(payload: dict, *keys: str) -> None:
    """Validate a payload has all required keys (else a retryable ChainError)."""
    missing = [k for k in keys if k not in payload or payload[k] is None]
    if missing:
        raise ChainError(f"Malformed outbox payload: missing {', '.join(missing)}")


async def reap_unknown_topics(session: AsyncSession, known_topics: tuple[str, ...]) -> int:
    """Fail outbox rows whose topic no worker consumes.

    Without this, a row with an unknown/misspelled topic sits ``pending``
    forever (``_claim`` filters to known topics) — a silent loss of a financial
    event. Marking it ``failed`` surfaces it in admin views instead.
    """
    from app.models.wallet import TransactionOutbox

    if not known_topics:
        return 0
    stmt = (
        select(TransactionOutbox)
        .where(
            TransactionOutbox.status == "pending",
            TransactionOutbox.topic.not_in(known_topics),
        )
        .with_for_update(skip_locked=True)
    )
    rows = (await session.execute(stmt)).scalars().all()
    for item in rows:
        item.status = "failed"
        item.attempts += 1
        item.last_error = f"Unknown outbox topic: {item.topic}"
        item.processed_at = datetime.now(UTC)
    if rows:
        await session.flush()
        log.warning("outbox_unknown_topics_failed", count=len(rows))
    return len(rows)


async def process_outbox_item(session: AsyncSession, outbox_id: uuid.UUID) -> bool:
    from app.models.wallet import TransactionOutbox

    item = await session.get(TransactionOutbox, outbox_id)
    if item is None or item.status in ("done", "failed"):
        return False

    client = get_chain_client()
    tx = await _existing_tx(session, item.idempotency_key)
    if tx is None:
        payload0 = item.payload or {}
        asset_key = str(payload0.get("asset", "OPT")).upper()
        tx = BlockchainTransaction(
            idempotency_key=item.idempotency_key,
            network=settings.blockchain_network,
            chain_id=settings.chain_id,
            from_address=settings.treasury_address or "0x" + "0" * 40,
            contract_address=settings.asset_address(asset_key) or None,
            method=item.topic,
            arguments=item.payload,
            status="queued",
        )
        session.add(tx)
        await session.flush()

    try:
        try:
            if item.topic == "reward":
                payload = item.payload or {}
                _require(payload, "reward_key", "amount")
                receipt = await client.reward_user(
                    reward_key=payload["reward_key"],
                    user_ref=payload.get("user_ref", ""),
                    amount=int(payload["amount"]),
                    reason=payload.get("reward_type", "reward"),
                    asset=payload.get("asset", "OPT"),
                )
                tx.method = "rewardUser"
                if payload.get("allocation_id"):
                    allocation = await session.get(
                        RewardAllocation, uuid.UUID(payload["allocation_id"])
                    )
                    if allocation is not None:
                        allocation.blockchain_transaction_id = tx.id
            elif item.topic == "airdrop":
                # Router/mint payout of an asset to a recipient (OPT/QTC/ORT).
                payload = item.payload or {}
                _require(payload, "to", "amount")
                receipt = await client.mint(
                    to=payload["to"],
                    amount=int(payload["amount"]),
                    asset=payload.get("asset", "OPT"),
                )
                tx.method = "mint"
            elif item.topic == "withdrawal":
                # A withdrawal removes the amount from circulation on-chain. The
                # backend operator signs the burn, so it must burn from its OWN
                # account (the operator holds the pooled tokens); burning from
                # the treasury address would revert (operator is not approved).
                payload = item.payload or {}
                _require(payload, "amount")
                receipt = await client.burn(
                    from_=payload.get("from", client.operator_address),
                    amount=int(payload["amount"]),
                    asset=payload.get("asset", "OPT"),
                )
                tx.method = "burn"
                if payload.get("withdrawal_id"):
                    wd = await session.get(WithdrawalRequest, uuid.UUID(payload["withdrawal_id"]))
                    if wd is not None:
                        wd.blockchain_transaction_id = tx.id
                        wd.status = "submitted"
            elif item.topic in ("pause", "unpause"):
                payload = item.payload or {}
                if item.topic == "pause":
                    receipt = await client.pause(asset=payload.get("asset", "OPT"))
                    tx.method = "pause"
                else:
                    receipt = await client.unpause(asset=payload.get("asset", "OPT"))
                    tx.method = "unpause"
            elif item.topic == "swap":
                # ORX router: convert OPT into QTC/ORT.
                payload = item.payload or {}
                _require(payload, "asset", "amount")
                receipt = await client.swap_opt_for(
                    asset=payload["asset"], amount=int(payload["amount"])
                )
                tx.method = "swapOptFor"
            elif item.topic == "ai_request":
                # ORX router: burn ORT for AI usage (1 request = 1 ORT).
                payload = item.payload or {}
                _require(payload, "requests")
                receipt = await client.pay_ai_request(requests=int(payload["requests"]))
                tx.method = "payAiRequest"
            else:
                raise ChainError(f"Unknown outbox topic: {item.topic}")
        except (KeyError, ValueError) as exc:
            # A malformed payload / bad value must be retryable, not a crash.
            raise ChainError(f"Malformed outbox payload: {exc}") from exc

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
        # Back off before retrying so a persistently failing item does not spin
        # the poll loop; give up after max_attempts.
        from datetime import timedelta

        delay = min(300, 2 ** min(item.attempts, 8))
        item.available_at = datetime.now(UTC) + timedelta(seconds=delay)
        tx.status = "failed"
        tx.error_code = "chain_error"
        tx.error_message = str(exc)
        from app.core import metrics

        metrics.incr("blockchain_failed_transactions_total", topic=item.topic)
        if item.attempts >= item.max_attempts:
            item.status = "failed"
            await _mark_failed(session, item, str(exc))
        await session.flush()
        log.warning("outbox_failed", topic=item.topic, error=str(exc))
        return False


async def _mark_failed(session: AsyncSession, item, error: str) -> None:
    """Terminal failure: flag the allocation/withdrawal and refund the ledger."""
    from app.services.reward_engine import RewardEngine

    payload = item.payload or {}
    engine = RewardEngine(session)
    if item.topic == "reward" and payload.get("allocation_id"):
        allocation = await session.get(RewardAllocation, uuid.UUID(payload["allocation_id"]))
        if allocation is not None and allocation.status != "cancelled":
            allocation.status = "failed"
            allocation.error_message = error
            # The user was credited off-chain; reverse it so the ledger and the
            # (absent) on-chain token stay consistent.
            await engine.refund_reward(
                user_id=allocation.user_id,
                amount=allocation.amount,
                allocation_id=allocation.id,
            )
    if item.topic == "withdrawal" and payload.get("withdrawal_id"):
        wd = await session.get(WithdrawalRequest, uuid.UUID(payload["withdrawal_id"]))
        if wd is not None and wd.status not in ("completed", "cancelled"):
            wd.status = "failed"
            # Funds were debited up front; return them to the user.
            await engine.refund_withdrawal(
                user_id=wd.user_id, amount=wd.amount, withdrawal_id=wd.id
            )
    if item.topic == "swap":
        await _refund_swap(engine, item, payload)
    if item.topic == "ai_request" and payload.get("user_id"):
        await engine.refund_ai_request(
            user_id=uuid.UUID(payload["user_id"]), requests=int(payload.get("requests", 0))
        )


async def _refund_swap(engine, item, payload: dict) -> None:
    """Return a failed swap's OPT and claw back the credited target asset."""
    if not payload.get("user_id"):
        return
    await engine.refund_swap(
        user_id=uuid.UUID(payload["user_id"]),
        opt_cost=int(payload.get("opt_cost", 0)),
        asset=str(payload.get("asset", "")),
        asset_amount=int(payload.get("amount", 0)),
        swap_key=item.idempotency_key,
    )


async def refresh_confirmations(session: AsyncSession, limit: int = 50) -> int:
    """Indexer helper: update confirmation counts + confirm/complete rows."""
    client = get_chain_client()
    stmt = (
        select(BlockchainTransaction)
        .where(BlockchainTransaction.status.in_(("submitted", "pending")))
        .order_by(BlockchainTransaction.created_at)
        .limit(limit)
        # SKIP LOCKED so two indexer replicas never process the same tx: without
        # it, both could pass the event existence check and collide on the
        # (transaction_hash, log_index) unique constraint, aborting the batch.
        .with_for_update(skip_locked=True)
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
                await _record_event(session, tx)
            elif receipt is not None and receipt.status == 0:
                tx.status = "failed"
                tx.error_code = "reverted"
                tx.error_message = "Transaction reverted"
                await _mark_reverted(session, tx)
        updated += 1
    await session.flush()
    return updated


async def _record_event(session: AsyncSession, tx: BlockchainTransaction) -> None:
    """Persist an indexer event row so /blockchain/events is populated.

    log_index is derived deterministically (0 for a tx's single log) and the
    (transaction_hash, log_index) pair is unique, so re-indexing is idempotent.
    """
    from app.models.wallet import BlockchainEvent

    if not tx.transaction_hash:
        return
    exists = (
        await session.execute(
            select(BlockchainEvent).where(BlockchainEvent.transaction_hash == tx.transaction_hash)
        )
    ).scalar_one_or_none()
    if exists is not None:
        return
    session.add(
        BlockchainEvent(
            contract_address=tx.contract_address or "",
            event_name=f"{tx.method}Confirmed",
            transaction_hash=tx.transaction_hash,
            log_index=0,
            block_number=tx.block_number or 0,
            args={"method": tx.method, "arguments": tx.arguments},
            processed=True,
        )
    )
    await session.flush()


async def _mark_reverted(session: AsyncSession, tx: BlockchainTransaction) -> None:
    """A reverted tx must reverse its financial effect and flag the source row."""
    from app.services.reward_engine import RewardEngine

    args = tx.arguments or {}
    engine = RewardEngine(session)
    if tx.method == "rewardUser" and args.get("allocation_id"):
        allocation = await session.get(RewardAllocation, uuid.UUID(args["allocation_id"]))
        if allocation is not None and allocation.status != "cancelled":
            allocation.status = "failed"
            allocation.error_message = "Transaction reverted"
            await engine.refund_reward(
                user_id=allocation.user_id,
                amount=allocation.amount,
                allocation_id=allocation.id,
            )
    if tx.method == "burn" and args.get("withdrawal_id"):
        wd = await session.get(WithdrawalRequest, uuid.UUID(args["withdrawal_id"]))
        if wd is not None and wd.status not in ("completed", "cancelled"):
            wd.status = "failed"
            await engine.refund_withdrawal(
                user_id=wd.user_id, amount=wd.amount, withdrawal_id=wd.id
            )
    if tx.method == "swapOptFor" and args.get("user_id"):
        await engine.refund_swap(
            user_id=uuid.UUID(args["user_id"]),
            opt_cost=int(args.get("opt_cost", 0)),
            asset=str(args.get("asset", "")),
            asset_amount=int(args.get("amount", 0)),
            swap_key=tx.idempotency_key,
        )
    if tx.method == "payAiRequest" and args.get("user_id"):
        await engine.refund_ai_request(
            user_id=uuid.UUID(args["user_id"]), requests=int(args.get("requests", 0))
        )


async def _mark_confirmed(session: AsyncSession, tx: BlockchainTransaction) -> None:
    args = tx.arguments or {}
    if tx.method == "rewardUser" and args.get("allocation_id"):
        allocation = await session.get(RewardAllocation, uuid.UUID(args["allocation_id"]))
        if allocation is not None:
            allocation.status = "confirmed"
            allocation.confirmed_at = datetime.now(UTC)
    if tx.method == "burn" and args.get("withdrawal_id"):
        wd = await session.get(WithdrawalRequest, uuid.UUID(args["withdrawal_id"]))
        if wd is not None:
            wd.status = "completed"
