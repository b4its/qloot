"""Wallet endpoints: balance, ledger, rewards, transfers, withdrawals."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError
from app.db.session import transaction
from app.models.identity import User
from app.models.wallet import RewardAllocation, WalletLedgerEntry, WithdrawalRequest
from app.schemas.wallet import (
    AIRequestIn,
    AssetBalanceOut,
    LedgerEntryOut,
    RewardOut,
    SwapRequestIn,
    TransferRequest,
    WalletAddressUpdate,
    WalletAssetsOut,
    WalletOut,
    WithdrawalOut,
    WithdrawalRequestIn,
)
from app.services.keys import tx_idempotency_key, withdrawal_key
from app.services.reward_engine import RewardEngine
from app.services.wallet_service import effective_wallet_address, set_wallet_address

router = APIRouter()

# Assets a user can obtain by swapping OPT through the OryphemProxy.
SWAPPABLE_ASSETS = ("QTC", "ORT")


def _asset_balance_out(asset: str, balance: int) -> AssetBalanceOut:
    meta = settings.ASSET_META.get(asset, {"name": asset, "symbol": asset, "role": ""})
    return AssetBalanceOut(
        asset=asset, name=meta["name"], symbol=meta["symbol"], balance=balance, role=meta["role"]
    )


async def _account_out(db, user: User) -> WalletOut:
    engine = RewardEngine(db)
    account = await engine.get_or_create_account(user.id)
    return WalletOut(
        user_id=user.id,
        token_id=account.token_id,
        available=account.cached_balance,
        pending=account.cached_pending,
        # Only the caller's *own* wallet address is exposed — the shared
        # platform treasury address is never surfaced to users.
        withdrawal_address=effective_wallet_address(account),
        network=settings.blockchain_network,
    )


@router.get("", response_model=WalletOut)
async def get_wallet(user: CurrentUser, db: DbSession):
    return await _account_out(db, user)


@router.get("/assets", response_model=WalletAssetsOut)
async def get_wallet_assets(user: CurrentUser, db: DbSession):
    """Per-asset balances for the caller (OPT from the ledger, QTC/ORT cached)."""
    engine = RewardEngine(db)
    account = await engine.get_or_create_account(user.id)
    assets = [
        _asset_balance_out("OPT", account.cached_balance),
        _asset_balance_out("QTC", await engine.asset_balance(user.id, "QTC")),
        _asset_balance_out("ORT", await engine.asset_balance(user.id, "ORT")),
    ]
    return WalletAssetsOut(user_id=user.id, network=settings.blockchain_network, assets=assets)


@router.post("/swap", response_model=WalletAssetsOut)
async def swap_opt(payload: SwapRequestIn, user: CurrentUser, db: DbSession):
    """Convert OPT into QTC/ORT through the OryphemProxy (ORX).

    Debits the OPT cost from the ledger, credits the target asset balance and
    enqueues an on-chain `swap` outbox item (the worker performs the real
    `swapOptFor` on the router).
    """
    asset = payload.asset.upper()
    rate = settings.orx_rate(asset)
    opt_cost = rate * payload.amount

    async with transaction(db):
        engine = RewardEngine(db)
        account = await engine.get_or_create_account(user.id)
        if account.is_frozen:
            raise ConflictError("Wallet is frozen")
        if account.cached_balance < opt_cost:
            raise ConflictError("Insufficient OPT balance")
        # Debit OPT + credit target atomically.
        await engine.debit_for_withdrawal(
            user=user,
            amount=opt_cost,
            withdrawal_id=uuid.uuid4(),
            destination=f"ORX:{asset}",
        )
        await engine.credit_asset(user_id=user.id, asset=asset, amount=payload.amount)

        from app.models.wallet import TransactionOutbox

        nonce = uuid.uuid4().hex[:16]
        db.add(
            TransactionOutbox(
                topic="swap",
                idempotency_key=tx_idempotency_key("swap", str(user.id), asset, nonce)[:64],
                payload={
                    "asset": asset,
                    "amount": payload.amount,
                    "opt_cost": opt_cost,
                    "user_ref": user.chain_user_ref,
                },
                status="pending",
            )
        )
        await db.flush()
        out = await _assets_out(db, user, engine)
    return out


async def _assets_out(db, user: User, engine: RewardEngine) -> WalletAssetsOut:
    account = await engine.get_or_create_account(user.id)
    return WalletAssetsOut(
        user_id=user.id,
        network=settings.blockchain_network,
        assets=[
            _asset_balance_out("OPT", account.cached_balance),
            _asset_balance_out("QTC", await engine.asset_balance(user.id, "QTC")),
            _asset_balance_out("ORT", await engine.asset_balance(user.id, "ORT")),
        ],
    )


@router.post("/ai-requests", response_model=WalletAssetsOut)
async def pay_ai_requests(payload: AIRequestIn, user: CurrentUser, db: DbSession):
    """Spend ORT on AI usage (1 request = 1 ORT).

    Debits ORT from the user's balance and enqueues an on-chain `ai_request`
    outbox item (the worker burns ORT via the OryphemProxy).
    """
    async with transaction(db):
        engine = RewardEngine(db)
        await engine.debit_asset(user_id=user.id, asset="ORT", amount=payload.requests)

        from app.models.wallet import TransactionOutbox

        nonce = uuid.uuid4().hex[:16]
        db.add(
            TransactionOutbox(
                topic="ai_request",
                idempotency_key=tx_idempotency_key("ai_request", str(user.id), nonce)[:64],
                payload={
                    "requests": payload.requests,
                    "user_ref": user.chain_user_ref,
                },
                status="pending",
            )
        )
        await db.flush()
        out = await _assets_out(db, user, engine)
    return out


@router.patch("/address", response_model=WalletOut)
async def update_wallet_address(payload: WalletAddressUpdate, user: CurrentUser, db: DbSession):
    """Change your own personal withdrawal wallet.

    Object-level guard: a user may only change *their* wallet (no admin override
    — this is a self-service setting). Addresses are EIP-55 checksummed and the
    change is recorded in the audit log.
    """
    async with transaction(db):
        await set_wallet_address(db, user, payload.address, source=payload.source)
        result = await _account_out(db, user)
    return result


@router.get("/transfer-recipients", response_model=list[dict])
async def transfer_recipients(user: CurrentUser, db: DbSession, q: str = "", limit: LimitParam = 8):
    """Search active users to transfer OPT to (simulated directory)."""
    stmt = select(User).where(User.is_active.is_(True), User.id != user.id)
    term = q.strip()
    if term:
        like = f"%{term.lower()}%"
        stmt = stmt.where(
            (func.lower(User.full_name).like(like)) | (func.lower(User.email).like(like))
        )
    stmt = stmt.order_by(User.full_name).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"user_id": str(u.id), "full_name": u.full_name, "email": u.email} for u in rows]


@router.get("/ledger", response_model=list[LedgerEntryOut])
async def get_ledger(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    engine = RewardEngine(db)
    account = await engine.get_or_create_account(user.id)
    stmt = (
        select(WalletLedgerEntry)
        .where(WalletLedgerEntry.account_id == account.id)
        .order_by(WalletLedgerEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get("/rewards", response_model=list[RewardOut])
async def my_rewards(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    stmt = (
        select(RewardAllocation)
        .where(RewardAllocation.user_id == user.id)
        .order_by(RewardAllocation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        RewardOut(
            id=r.id,
            reward_key=r.reward_key,
            reward_type=r.reward_type,
            rank=r.rank,
            amount=r.amount,
            status=r.status,
            quest_id=r.quest_id,
            task_id=r.task_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/reconciliation")
async def reconciliation(user: CurrentUser, db: DbSession):
    engine = RewardEngine(db)
    cached, computed = await engine.reconcile(user.id)
    return {"cached_balance": cached, "computed_balance": computed, "ok": cached == computed}


@router.post("/transfers", response_model=WalletOut)
async def transfer(payload: TransferRequest, user: CurrentUser, db: DbSession):
    """Internal ledger transfer between two users (no on-chain tx)."""
    if payload.to_user_id == user.id:
        raise ConflictError("Cannot transfer to yourself")
    async with transaction(db):
        recipient = await db.get(User, payload.to_user_id)
        if recipient is None:
            raise NotFoundError("Recipient not found")
        engine = RewardEngine(db)
        # Lock both wallet rows in a deterministic (user_id) order *before*
        # debiting/crediting. Otherwise simultaneous A->B and B->A transfers
        # grab the two row locks in opposite order and Postgres deadlocks them.
        lo, hi = sorted((user.id, recipient.id), key=str)
        await engine.get_or_create_account(lo)
        if hi != lo:
            await engine.get_or_create_account(hi)
        account = await engine.get_or_create_account(user.id)
        # A frozen account must not be able to move funds out (credit() already
        # blocks a frozen recipient; this covers the sender/debit side).
        if account.is_frozen:
            raise ConflictError("Wallet is frozen")
        if account.cached_balance < payload.amount:
            raise ConflictError("Insufficient balance")
        # Every transfer needs a unique reference: include a nonce so repeated
        # transfers to the same recipient do not collide on the ledger's
        # (reference_type, reference_id, entry_type) uniqueness.
        nonce = uuid.uuid4().hex[:16]
        ref = tx_idempotency_key("transfer", str(user.id), str(payload.to_user_id), nonce)[:64]
        from app.models.wallet import WalletLedgerEntry as LE

        account.cached_balance -= payload.amount
        db.add(
            LE(
                account_id=account.id,
                token_id=account.token_id,
                entry_type="debit",
                amount=payload.amount,
                balance_after=account.cached_balance,
                reference_type="transfer_out",
                reference_id=ref,
                description=payload.note or "Internal transfer",
            )
        )
        await engine.credit(
            user=recipient,
            amount=payload.amount,
            reference_type="transfer_in",
            reference_id=ref,
            reward_key_value="",
            token_id=account.token_id,
            description=payload.note or f"Transfer from {user.id}",
        )
        result = await _account_out(db, user)
    return result


@router.post("/withdrawals", response_model=WithdrawalOut, status_code=status.HTTP_201_CREATED)
async def request_withdrawal(payload: WithdrawalRequestIn, user: CurrentUser, db: DbSession):
    async with transaction(db):
        engine = RewardEngine(db)
        account = await engine.get_or_create_account(user.id)
        if account.cached_balance < payload.amount:
            raise ConflictError("Insufficient balance")
        wd = WithdrawalRequest(
            user_id=user.id,
            reward_key=withdrawal_key(uuid.uuid4()),
            destination_address=payload.destination_address,
            token_id=account.token_id,
            amount=payload.amount,
            status="requested",
        )
        db.add(wd)
        await db.flush()
        wd.reward_key = withdrawal_key(wd.id)
        await engine.debit_for_withdrawal(
            user=user,
            amount=payload.amount,
            withdrawal_id=wd.id,
            destination=payload.destination_address,
        )
        from app.models.wallet import TransactionOutbox

        db.add(
            TransactionOutbox(
                topic="withdrawal",
                idempotency_key=tx_idempotency_key("withdrawal", str(wd.id)),
                payload={
                    "withdrawal_id": str(wd.id),
                    "user_ref": user.chain_user_ref,
                    "destination": payload.destination_address,
                    "amount": payload.amount,
                    "token_id": account.token_id,
                    "asset": "OPT",
                },
                status="pending",
            )
        )
        await db.flush()
    return WithdrawalOut.model_validate(wd)


@router.get("/withdrawals/{withdrawal_id}", response_model=WithdrawalOut)
async def get_withdrawal(withdrawal_id: uuid.UUID, user: CurrentUser, db: DbSession):
    wd = await db.get(WithdrawalRequest, withdrawal_id)
    if wd is None or (wd.user_id != user.id and not user.has_role("admin")):
        raise NotFoundError("Withdrawal not found")
    return WithdrawalOut.model_validate(wd)
