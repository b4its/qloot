"""Withdrawal approval state machine.

    requested ──approve──► approved ──(worker submits)──► submitted ──► confirmed
        │                       │                                 └─► failed
        ├──reject──► rejected
        └──cancel──► cancelled   (user, while still ``requested``)

The amount (plus any flat fee) is debited at request time so funds cannot be
double-spent; approving enqueues the on-chain ``withdrawal`` outbox item.
Rejection and cancellation return the funds (amount + fee) to the user.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.identity import AuditLog, User
from app.models.wallet import TransactionOutbox, WithdrawalRequest
from app.services.keys import tx_idempotency_key, withdrawal_key
from app.services.reward_engine import RewardEngine

log = get_logger("withdrawals")

# Statuses that no longer allow a user-side cancel.
_CANCELLABLE = {"requested"}


class WithdrawalService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _rolling_24h_total(self, user_id: uuid.UUID) -> int:
        """Sum of non-terminal withdrawal amounts in the last 24h."""
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        total = (
            await self.session.execute(
                select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(
                    WithdrawalRequest.user_id == user_id,
                    WithdrawalRequest.created_at >= cutoff,
                    WithdrawalRequest.status.in_(
                        ("requested", "approved", "submitted", "confirmed")
                    ),
                )
            )
        ).scalar_one()
        return int(total)

    async def request(
        self, *, user: User, destination: str, amount: int
    ) -> WithdrawalRequest:
        if amount < settings.withdrawal_min_amount:
            raise ValidationError(
                f"Minimum withdrawal is {settings.withdrawal_min_amount}"
            )
        if amount > settings.withdrawal_max_amount:
            raise ValidationError(
                f"Maximum withdrawal is {settings.withdrawal_max_amount}"
            )
        if await self._rolling_24h_total(user.id) + amount > settings.withdrawal_daily_limit:
            raise ConflictError("Daily withdrawal limit exceeded")

        fee = settings.withdrawal_fee
        engine = RewardEngine(self.session)
        account = await engine.get_or_create_account(user.id)
        if account.is_frozen:
            raise ConflictError("Wallet is frozen")
        total = amount + fee
        if account.cached_balance < total:
            raise ConflictError("Insufficient balance")

        wd = WithdrawalRequest(
            user_id=user.id,
            reward_key=withdrawal_key(uuid.uuid4()),
            destination_address=destination,
            token_id=account.token_id,
            amount=amount,
            fee_amount=fee,
            status="requested",
        )
        self.session.add(wd)
        await self.session.flush()
        wd.reward_key = withdrawal_key(wd.id)

        # Debit the amount (its own ledger entry) and the fee separately.
        await engine.debit_for_withdrawal(
            user=user, amount=amount, withdrawal_id=wd.id, destination=destination
        )
        if fee > 0:
            await engine.debit_withdrawal_fee(
                user_id=user.id, amount=fee, withdrawal_id=wd.id
            )
        await self.session.flush()
        log.info("withdrawal_requested", withdrawal_id=str(wd.id), amount=amount, fee=fee)
        return wd

    async def approve(
        self, *, admin: User, withdrawal_id: uuid.UUID
    ) -> WithdrawalRequest:
        wd = await self.session.get(WithdrawalRequest, withdrawal_id)
        if wd is None:
            raise NotFoundError("Withdrawal not found")
        if wd.status != "requested":
            raise ConflictError(f"Withdrawal is {wd.status}, not pending review")

        wd.status = "approved"
        wd.reviewed_by = admin.id
        wd.reviewed_at = datetime.now(UTC)
        self.session.add(
            AuditLog(
                actor_id=admin.id,
                action="withdrawal.approve",
                entity_type="withdrawal",
                entity_id=str(wd.id),
                data={"amount": wd.amount, "fee": wd.fee_amount},
            )
        )
        # Enqueue the on-chain burn only now (approval is the gate).
        self.session.add(
            TransactionOutbox(
                topic="withdrawal",
                idempotency_key=tx_idempotency_key("withdrawal", str(wd.id)),
                payload={
                    "withdrawal_id": str(wd.id),
                    "user_ref": (await self.session.get(User, wd.user_id)).chain_user_ref
                    if wd.user_id
                    else "",
                    "destination": wd.destination_address,
                    "amount": wd.amount,
                    "token_id": wd.token_id,
                    "asset": "OPT",
                },
                status="pending",
            )
        )
        await self.session.flush()
        log.info("withdrawal_approved", withdrawal_id=str(wd.id), admin=str(admin.id))
        return wd

    async def reject(
        self, *, admin: User, withdrawal_id: uuid.UUID, reason: str | None
    ) -> WithdrawalRequest:
        wd = await self.session.get(WithdrawalRequest, withdrawal_id)
        if wd is None:
            raise NotFoundError("Withdrawal not found")
        if wd.status != "requested":
            raise ConflictError(f"Withdrawal is {wd.status}, not pending review")
        wd.status = "rejected"
        wd.reject_reason = reason
        wd.reviewed_by = admin.id
        wd.reviewed_at = datetime.now(UTC)
        self.session.add(
            AuditLog(
                actor_id=admin.id,
                action="withdrawal.reject",
                entity_type="withdrawal",
                entity_id=str(wd.id),
                data={"reason": reason},
            )
        )
        await self._refund(wd)
        log.info("withdrawal_rejected", withdrawal_id=str(wd.id), admin=str(admin.id))
        return wd

    async def cancel(self, *, user: User, withdrawal_id: uuid.UUID) -> WithdrawalRequest:
        wd = await self.session.get(WithdrawalRequest, withdrawal_id)
        if wd is None or wd.user_id != user.id:
            raise NotFoundError("Withdrawal not found")
        if wd.status not in _CANCELLABLE:
            raise ConflictError("Only a pending withdrawal can be cancelled")
        wd.status = "cancelled"
        wd.reviewed_at = datetime.now(UTC)
        await self._refund(wd)
        log.info("withdrawal_cancelled", withdrawal_id=str(wd.id), user=str(user.id))
        return wd

    async def _refund(self, wd: WithdrawalRequest) -> None:
        """Return the amount (and any fee) to the user (idempotent)."""
        engine = RewardEngine(self.session)
        await engine.refund_withdrawal(
            user_id=wd.user_id, amount=wd.amount, withdrawal_id=wd.id
        )
        if wd.fee_amount:
            await engine.refund_withdrawal_fee(
                user_id=wd.user_id, amount=wd.fee_amount, withdrawal_id=wd.id
            )
        await self.session.flush()

    async def list_for_admin(
        self, *, status: str | None, limit: int, offset: int
    ) -> list[WithdrawalRequest]:
        stmt = select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())
        if status:
            stmt = stmt.where(WithdrawalRequest.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    def ensure_reviewable(self, wd: WithdrawalRequest, admin: User) -> None:
        if not admin.has_role("admin"):
            raise ForbiddenError("Admin only")
