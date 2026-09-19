"""Blockchain endpoints: status, transactions, events, contract info."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.blockchain.client import get_chain_client
from app.core.errors import NotFoundError
from app.models.wallet import BlockchainEvent, BlockchainTransaction, ContractDeployment

router = APIRouter()


@router.get("/status")
async def status(user: CurrentUser):
    return get_chain_client().status()


@router.get("/contract")
async def contract(db: DbSession, user: CurrentUser):
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
        "client": get_chain_client().status(),
    }


@router.get("/transactions")
async def transactions(db: DbSession, user: CurrentUser, limit: int = 100, offset: int = 0):
    stmt = (
        select(BlockchainTransaction)
        .order_by(BlockchainTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
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
async def transaction_detail(tx_hash: str, db: DbSession, user: CurrentUser):
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
async def events(db: DbSession, user: CurrentUser, limit: int = 100, offset: int = 0):
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
async def allocations(db: DbSession, user: CurrentUser, limit: int = 100):
    from app.models.wallet import RewardAllocation

    stmt = select(RewardAllocation).order_by(RewardAllocation.created_at.desc()).limit(limit)
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
