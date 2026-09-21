"""Blockchain endpoints: status, transactions, events, contract info."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession, LimitParam, OffsetParam
from app.blockchain.client import get_chain_client
from app.core.errors import NotFoundError
from app.models.wallet import (
    BlockchainEvent,
    BlockchainTransaction,
    ContractDeployment,
    RewardAllocation,
    WithdrawalRequest,
)

router = APIRouter()


@router.get("/status")
async def status(user: CurrentUser):
    """Address-free chain status (safe for any authenticated user)."""
    return get_chain_client().status()


@router.get("/status/admin")
async def admin_status(admin: AdminUser):
    """Full chain status incl. contract/treasury addresses (admin only)."""
    return get_chain_client().admin_status()


@router.get("/contract")
async def contract(db: DbSession, admin: AdminUser):
    stmt = select(ContractDeployment).where(ContractDeployment.is_active.is_(True))
    deployments = (await db.execute(stmt)).scalars().all()
    return {
        "deployments": [
            {
                "network": d.network,
                "chain_id": d.chain_id,
                "name": d.name,
                "address": d.address,
                "treasury": d.treasury,
                "tx_hash": d.tx_hash,
            }
            for d in deployments
        ],
        "client": get_chain_client().admin_status(),
    }


@router.get("/transactions")
async def transactions(
    db: DbSession, user: CurrentUser, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """On-chain transactions.

    Admins see every transaction; other users only see transactions linked to
    their own reward allocations or withdrawals (never the global firehose).
    """
    stmt = select(BlockchainTransaction).order_by(BlockchainTransaction.created_at.desc())
    if not user.has_role("admin"):
        reward_tx = select(RewardAllocation.blockchain_transaction_id).where(
            RewardAllocation.user_id == user.id,
            RewardAllocation.blockchain_transaction_id.is_not(None),
        )
        wd_tx = select(WithdrawalRequest.blockchain_transaction_id).where(
            WithdrawalRequest.user_id == user.id,
            WithdrawalRequest.blockchain_transaction_id.is_not(None),
        )
        stmt = stmt.where(BlockchainTransaction.id.in_(reward_tx.union(wd_tx)))
    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    client = get_chain_client()
    return [
        {
            "id": str(t.id),
            "method": t.method,
            "status": t.status,
            "network": t.network,
            "chain_id": t.chain_id,
            "transaction_hash": t.transaction_hash,
            "block_number": t.block_number,
            "confirmation_count": t.confirmation_count,
            "explorer_url": client.explorer_url(t.transaction_hash) if t.transaction_hash else None,
            "created_at": t.created_at,
        }
        for t in rows
    ]


@router.get("/transactions/{tx_hash}")
async def transaction_detail(tx_hash: str, db: DbSession, admin: AdminUser):
    stmt = select(BlockchainTransaction).where(BlockchainTransaction.transaction_hash == tx_hash)
    tx = (await db.execute(stmt)).scalar_one_or_none()
    if tx is None:
        raise NotFoundError("Transaction not found")
    client = get_chain_client()
    events = (
        (
            await db.execute(
                select(BlockchainEvent).where(BlockchainEvent.transaction_hash == tx_hash)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(tx.id),
        "method": tx.method,
        "status": tx.status,
        "transaction_hash": tx.transaction_hash,
        "block_number": tx.block_number,
        "confirmation_count": tx.confirmation_count,
        "gas_used": tx.gas_used,
        "error_message": tx.error_message,
        "explorer_url": client.explorer_url(tx.transaction_hash) if tx.transaction_hash else None,
        "events": [{"name": e.event_name, "args": e.args} for e in events],
    }


@router.get("/events")
async def events(db: DbSession, admin: AdminUser, limit: LimitParam = 100, offset: OffsetParam = 0):
    stmt = (
        select(BlockchainEvent)
        .order_by(BlockchainEvent.block_number.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "name": e.event_name,
            "transaction_hash": e.transaction_hash,
            "block_number": e.block_number,
            "log_index": e.log_index,
            "args": e.args,
        }
        for e in rows
    ]


@router.get("/allocations")
async def allocations(
    db: DbSession, admin: AdminUser, limit: LimitParam = 100, offset: OffsetParam = 0
):
    stmt = (
        select(RewardAllocation)
        .order_by(RewardAllocation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "reward_key": r.reward_key,
            "user_id": str(r.user_id),
            "amount": r.amount,
            "status": r.status,
            "quest_id": str(r.quest_id) if r.quest_id else None,
            "tx_id": str(r.blockchain_transaction_id) if r.blockchain_transaction_id else None,
        }
        for r in rows
    ]
