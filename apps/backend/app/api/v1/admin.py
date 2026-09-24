"""Admin endpoints: users, rewards, blockchain control, audit logs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession, LimitParam, OffsetParam
from app.blockchain.worker_logic import process_outbox_item
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.base import utcnow
from app.db.session import transaction
from app.models.identity import AuditLog, Role, User, UserRole
from app.models.quest import Quest
from app.models.wallet import RewardAllocation, TransactionOutbox
from app.schemas.auth import AdminUserCreate, UserOut
from app.services.audit import current_request_id

router = APIRouter()


# Assets that can be paused/unpaused on-chain (ORX is a router, not pausable).
_PAUSABLE_ASSETS = ("OPT", "QTC", "ORT")


def _validate_asset(asset: str) -> str:
    asset = (asset or "OPT").upper()
    if asset not in _PAUSABLE_ASSETS:
        raise ValidationError(f"asset must be one of {', '.join(_PAUSABLE_ASSETS)}")
    return asset


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(student|teacher|admin)$")


class ActiveUpdate(BaseModel):
    is_active: bool


class RejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class RewardAdjustRequest(BaseModel):
    """Manual, audited OPT balance adjustment."""

    user_id: uuid.UUID
    amount: int = Field(description="Positive grants, negative claws back")
    reason: str = Field(min_length=3, max_length=255)
    idempotency_key: str = Field(min_length=4, max_length=64)


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    entity_type: str | None
    entity_id: str | None
    data: dict | None
    created_at: object


@router.get("/users", response_model=list[UserOut])
async def list_users(
    admin: AdminUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    users = (await db.execute(stmt)).scalars().all()
    return [
        UserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            chain_user_ref=u.chain_user_ref,
            avatar_url=u.avatar_url,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
            roles=sorted(u.role_names),
        )
        for u in users
    ]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(payload: AdminUserCreate, admin: AdminUser, db: DbSession):
    """Create an account (any role). Reuses the auth service so wallet,
    roles and welcome notification are set up exactly like self-registration."""
    from app.services.auth_service import AuthService

    async with transaction(db):
        user, _token = await AuthService(db).register(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            role=payload.role,
            class_code=payload.class_code,
            class_type=payload.class_type,
            issue_session=False,
        )
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="user.create",
                entity_type="user",
                entity_id=str(user.id),
                data={"role": payload.role},
                request_id=current_request_id(),
            )
        )
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        chain_user_ref=user.chain_user_ref,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        roles=sorted(user.role_names),
        class_code=user.class_code,
        class_type=user.class_type,
    )


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def set_user_role(user_id: uuid.UUID, payload: RoleUpdate, admin: AdminUser, db: DbSession):
    async with transaction(db):
        user = await db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        role = (
            await db.execute(select(Role).where(Role.name == payload.role))
        ).scalar_one_or_none()
        if role is None:
            raise ValidationError("Unknown role")
        from sqlalchemy import delete

        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="user.role_change",
                entity_type="user",
                entity_id=str(user.id),
                data={"new_role": payload.role},
                request_id=current_request_id(),
            )
        )
        await db.flush()
        await db.refresh(user)
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        chain_user_ref=user.chain_user_ref,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        roles=sorted(user.role_names),
    )


@router.patch("/users/{user_id}/active", response_model=UserOut)
async def set_user_active(
    user_id: uuid.UUID, payload: ActiveUpdate, admin: AdminUser, db: DbSession
):
    """Activate/deactivate a user. Deactivation is the safe 'remove' — it keeps
    the ledger/audit history intact while blocking sign-in and API access."""
    async with transaction(db):
        user = await db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.id == admin.id and not payload.is_active:
            raise ValidationError("You cannot deactivate your own account")
        user.is_active = payload.is_active
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="user.activate" if payload.is_active else "user.deactivate",
                entity_type="user",
                entity_id=str(user.id),
                data={"is_active": payload.is_active},
                request_id=current_request_id(),
            )
        )
        await db.flush()
        await db.refresh(user)
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        chain_user_ref=user.chain_user_ref,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        roles=sorted(user.role_names),
    )


@router.get("/rewards")
async def list_rewards(
    admin: AdminUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
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
            "rank": r.rank,
            "token_id": r.token_id,
            "quest_id": str(r.quest_id) if r.quest_id else None,
            "task_id": str(r.task_id) if r.task_id else None,
            # Troubleshooting fields so an admin can see *why* a reward failed
            # and link to its on-chain transaction without DB access.
            "error_message": r.error_message,
            "blockchain_transaction_id": (
                str(r.blockchain_transaction_id) if r.blockchain_transaction_id else None
            ),
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/rewards/adjust")
async def adjust_reward(payload: RewardAdjustRequest, admin: AdminUser, db: DbSession):
    """Manually adjust a user's OPT balance (audited, idempotent).

    Writes exactly one ``admin_adjustment`` ledger entry keyed by
    ``idempotency_key`` (a repeat with the same key is a no-op) and an
    ``AuditLog`` row carrying the request id.
    """
    from app.services.reward_engine import RewardEngine

    async with transaction(db):
        target = await db.get(User, payload.user_id)
        if target is None:
            raise NotFoundError("User not found")
        await RewardEngine(db).admin_adjust(
            user=target,
            amount=payload.amount,
            adjust_key=payload.idempotency_key,
            reason=payload.reason,
        )
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="reward.adjust",
                entity_type="user",
                entity_id=str(target.id),
                data={
                    "amount": payload.amount,
                    "reason": payload.reason,
                    "idempotency_key": payload.idempotency_key,
                },
                request_id=current_request_id(),
            )
        )
    return {"status": "adjusted", "user_id": str(target.id), "amount": payload.amount}


@router.post("/rewards/{reward_id}/retry")
async def retry_reward(reward_id: uuid.UUID, admin: AdminUser, db: DbSession):
    async with transaction(db):
        allocation = await db.get(RewardAllocation, reward_id)
        if allocation is None:
            raise NotFoundError("Reward not found")
        if allocation.status in ("confirmed", "cancelled"):
            raise ConflictError(f"Cannot retry a {allocation.status} reward")
        # A previously-failed reward was refunded (its credit reversed); retrying
        # must restore the ledger credit so a *successful* retry leaves the user
        # whole. (`recredit_reward_retry` is idempotent.)
        if allocation.status == "failed":
            from app.services.reward_engine import RewardEngine

            await RewardEngine(db).recredit_reward_retry(
                user_id=allocation.user_id,
                amount=allocation.amount,
                allocation_id=allocation.id,
            )
        allocation.status = "pending"
        allocation.error_message = None
        from app.services.keys import quest_ref, tx_idempotency_key

        idem_key = tx_idempotency_key("reward", allocation.reward_key)
        outbox = (
            await db.execute(
                select(TransactionOutbox).where(TransactionOutbox.idempotency_key == idem_key)
            )
        ).scalar_one_or_none()
        if outbox is None:
            # Recreate an outbox item using the real user reference.
            user_row = await db.get(User, allocation.user_id)
            quest = await db.get(Quest, allocation.quest_id) if allocation.quest_id else None
            outbox = TransactionOutbox(
                topic="reward",
                idempotency_key=idem_key,
                payload={
                    "allocation_id": str(allocation.id),
                    "reward_key": allocation.reward_key,
                    "quest_ref": quest_ref(quest.id) if quest else "0x" + "0" * 64,
                    "user_ref": user_row.chain_user_ref if user_row else "0x" + "0" * 64,
                    "rank": allocation.rank or 0,
                    "amount": allocation.amount,
                    "token_id": allocation.token_id,
                },
                status="pending",
            )
            db.add(outbox)
            await db.flush()
        else:
            outbox.status = "pending"
            outbox.attempts = 0
            # available_at is NOT NULL: resetting to None crashed the retry.
            outbox.available_at = utcnow()
            await db.flush()
        ok = await process_outbox_item(db, outbox.id)
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="reward.retry",
                entity_type="reward_allocation",
                entity_id=str(allocation.id),
                data=None,
                request_id=current_request_id(),
            )
        )
    return {"status": "retried" if ok else "queued", "reward_id": str(reward_id)}


@router.post("/rewards/{reward_id}/cancel")
async def cancel_reward(reward_id: uuid.UUID, admin: AdminUser, db: DbSession):
    async with transaction(db):
        allocation = await db.get(RewardAllocation, reward_id)
        if allocation is None:
            raise NotFoundError("Reward not found")
        if allocation.status == "cancelled":
            return {"status": "cancelled", "reward_id": str(reward_id)}
        if allocation.status == "confirmed":
            raise ConflictError("Cannot cancel an already-confirmed (on-chain) reward")

        already_refunded = allocation.status == "failed"
        allocation.status = "cancelled"
        # Reverse the off-chain credit if it was never minted (and not already
        # reversed by a prior failure path).
        if not already_refunded:
            from app.services.reward_engine import RewardEngine

            await RewardEngine(db).refund_reward(
                user_id=allocation.user_id,
                amount=allocation.amount,
                allocation_id=allocation.id,
            )
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="reward.cancel",
                entity_type="reward_allocation",
                entity_id=str(allocation.id),
                data=None,
                request_id=current_request_id(),
            )
        )
    return {"status": "cancelled", "reward_id": str(reward_id)}


@router.post("/blockchain/pause")
async def blockchain_pause(admin: AdminUser, db: DbSession, asset: str = "OPT"):
    asset = _validate_asset(asset)
    async with transaction(db):
        db.add(
            TransactionOutbox(
                topic="pause",
                idempotency_key=f"pause-{asset}-{uuid.uuid4().hex}",
                payload={"action": "pause", "asset": asset},
                status="pending",
            )
        )
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="chain.pause",
                entity_type="contract",
                entity_id=asset,
                data={"asset": asset},
                request_id=current_request_id(),
            )
        )
    return {"status": "pause_queued", "asset": asset}


@router.post("/blockchain/unpause")
async def blockchain_unpause(admin: AdminUser, db: DbSession, asset: str = "OPT"):
    asset = _validate_asset(asset)
    async with transaction(db):
        db.add(
            TransactionOutbox(
                topic="unpause",
                idempotency_key=f"unpause-{asset}-{uuid.uuid4().hex}",
                payload={"action": "unpause", "asset": asset},
                status="pending",
            )
        )
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="chain.unpause",
                entity_type="contract",
                entity_id=asset,
                data={"asset": asset},
                request_id=current_request_id(),
            )
        )
    return {"status": "unpause_queued", "asset": asset}


@router.get("/audit-logs")
async def audit_logs(
    admin: AdminUser,
    db: DbSession,
    action: str | None = None,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(a.id),
            "actor_id": str(a.actor_id) if a.actor_id else None,
            "action": a.action,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "request_id": a.request_id,
            "data": a.data,
            "created_at": a.created_at,
        }
        for a in rows
    ]


@router.get("/config")
async def show_config(admin: AdminUser):
    """Non-secret configuration summary."""
    return {
        "env": settings.app_env,
        "ai_provider": settings.ai_provider,
        "blockchain": settings.blockchain_network,
        "dry_run": settings.blockchain_dry_run,
        "reward_ranks": settings.reward_ranks,
        "confirmations": settings.opc_confirmations,
    }


# --- withdrawal review -----------------------------------------------------
@router.post("/rewards/{reward_id}/cancel")


@router.get("/withdrawals")
async def list_withdrawals(
    admin: AdminUser,
    db: DbSession,
    status_filter: str | None = None,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    """Admin queue of withdrawal requests (optionally filtered by status)."""
    from app.services.withdrawal_service import WithdrawalService

    rows = await WithdrawalService(db).list_for_admin(
        status=status_filter, limit=limit, offset=offset
    )
    return [
        {
            "id": str(w.id),
            "user_id": str(w.user_id),
            "destination_address": w.destination_address,
            "amount": w.amount,
            "fee_amount": w.fee_amount,
            "status": w.status,
            "reject_reason": w.reject_reason,
            "created_at": w.created_at,
            "reviewed_at": w.reviewed_at,
        }
        for w in rows
    ]


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(withdrawal_id: uuid.UUID, admin: AdminUser, db: DbSession):
    """Approve a pending withdrawal (enqueues the on-chain burn)."""
    from app.services.withdrawal_service import WithdrawalService

    async with transaction(db):
        wd = await WithdrawalService(db).approve(admin=admin, withdrawal_id=withdrawal_id)
    return {"id": str(wd.id), "status": wd.status}


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: uuid.UUID, payload: RejectRequest, admin: AdminUser, db: DbSession
):
    """Reject a pending withdrawal (refunds the user)."""
    from app.services.withdrawal_service import WithdrawalService

    async with transaction(db):
        wd = await WithdrawalService(db).reject(
            admin=admin, withdrawal_id=withdrawal_id, reason=payload.reason
        )
    return {"id": str(wd.id), "status": wd.status}


@router.get("/ledger/negative")
async def negative_balances(
    admin: AdminUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """Accounts whose OPT balance went negative (clawback debt)."""
    from app.models.wallet import WalletAccount

    stmt = (
        select(WalletAccount)
        .where(WalletAccount.cached_balance < 0)
        .order_by(WalletAccount.cached_balance)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "account_id": str(a.id),
            "user_id": str(a.user_id),
            "cached_balance": a.cached_balance,
            "is_in_debt": a.is_in_debt,
            "is_frozen": a.is_frozen,
        }
        for a in rows
    ]


@router.post("/ledger/reconcile")
async def run_reconciliation(admin: AdminUser, db: DbSession):
    """Run a reconciliation sweep now; returns the accounts that had drifted."""
    from app.services.reward_engine import RewardEngine

    async with transaction(db):
        drifted = await RewardEngine(db).reconcile_all()
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="ledger.reconcile",
                entity_type="ledger",
                entity_id="all",
                data={"drifted": len(drifted)},
                request_id=current_request_id(),
            )
        )
    return {"drifted": drifted, "count": len(drifted)}
