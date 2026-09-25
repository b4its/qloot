"""Reward engine: allocation -> ledger credit -> outbox event (atomic).

This implements the §11.3 model:
  1. Create reward_allocation (idempotent on reward_key).
  2. Create double-entry ledger credit.
  3. Emit a transaction_outbox row.
  All in ONE database transaction, so a crash can never credit without an
  outbox event or vice versa. The blockchain worker drains the outbox.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ValidationError
from app.core.logging import get_logger
from app.models.identity import User
from app.models.quest import Quest
from app.models.wallet import (
    RewardAllocation,
    TransactionOutbox,
    WalletAccount,
    WalletAssetBalance,
    WalletLedgerEntry,
)
from app.services.keys import quest_ref, reward_key, tx_idempotency_key, user_ref

log = get_logger("rewards")


class RewardEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_account(self, user_id: uuid.UUID) -> WalletAccount:
        stmt = select(WalletAccount).where(WalletAccount.user_id == user_id).with_for_update()
        account = (await self.session.execute(stmt)).scalar_one_or_none()
        if account is None:
            from app.core.config import settings

            account = WalletAccount(
                user_id=user_id, withdrawal_address=(settings.default_wallet_address or None)
            )
            try:
                # SAVEPOINT so a concurrent insert only unwinds this attempt,
                # not the caller's whole unit of work.
                async with self.session.begin_nested():
                    self.session.add(account)
                    await self.session.flush()
            except IntegrityError:
                # Another request created the row first: fetch and lock it.
                account = (
                    await self.session.execute(
                        select(WalletAccount)
                        .where(WalletAccount.user_id == user_id)
                        .with_for_update()
                    )
                ).scalar_one()
        return account

    async def credit(
        self,
        *,
        user: User,
        amount: int,
        reference_type: str,
        reference_id: str,
        reward_key_value: str,
        token_id: int,
        description: str | None = None,
    ) -> WalletLedgerEntry:
        """Idempotently credit a user's custodial balance."""
        if amount <= 0:
            raise ConflictError("Reward amount must be positive")
        # Enforce the same per-transaction ceiling the on-chain contract applies
        # (opc_max_reward_per_tx) *before* writing the ledger, so we never mint
        # off-chain credit that the chain would reject and then have to reverse.
        from app.core.config import settings

        if amount > settings.opc_max_reward_per_tx:
            from app.core import metrics

            metrics.incr("reward_cap_rejections_total")
            raise ValidationError(
                f"Reward amount {amount} exceeds the per-transaction cap "
                f"of {settings.opc_max_reward_per_tx}"
            )

        account = await self.get_or_create_account(user.id)
        if account.is_frozen:
            raise ConflictError("Wallet is frozen")

        # Idempotency: a ledger entry for (reference_type, reference_id, credit)
        # may exist only once.
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == reference_type,
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "credit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup

        new_balance = account.cached_balance + amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=token_id,
            entry_type="credit",
            amount=amount,
            balance_after=new_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            reward_key=reward_key_value,
            description=description,
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        account.cached_pending = max(0, account.cached_pending - amount)
        await self._apply_negative_policy(account, "credit")
        await self.session.flush()
        return entry

    async def allocate_quest_reward(
        self,
        *,
        quest: Quest,
        user: User,
        rank: int,
        amount: int,
        score_bp: int,
    ) -> RewardAllocation:
        # A user may receive at most ONE reward per quest (enforced by
        # uq_reward_quest_user_type). If one exists, return it unchanged.
        existing = (
            await self.session.execute(
                select(RewardAllocation).where(
                    RewardAllocation.quest_id == quest.id,
                    RewardAllocation.user_id == user.id,
                    RewardAllocation.reward_type == "quest_rank",
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        rkey = reward_key(quest.id, user.id, rank, quest.reward_version)
        # Also guard on the exact reward key (covers version changes).
        by_key = (
            await self.session.execute(
                select(RewardAllocation).where(RewardAllocation.reward_key == rkey)
            )
        ).scalar_one_or_none()
        if by_key is not None:
            return by_key

        allocation = RewardAllocation(
            reward_key=rkey,
            user_id=user.id,
            quest_id=quest.id,
            reward_type="quest_rank",
            rank=rank,
            token_id=0,
            amount=amount,
            status="pending",
        )
        self.session.add(allocation)
        await self.session.flush()

        entry = await self.credit(
            user=user,
            amount=amount,
            reference_type="reward",
            reference_id=str(allocation.id),
            reward_key_value=rkey,
            token_id=0,
            description=f"Quest reward rank {rank} ({score_bp} bp)",
        )
        allocation.ledger_entry_id = entry.id

        # Outbox event -> blockchain worker.
        self.session.add(
            TransactionOutbox(
                topic="reward",
                idempotency_key=tx_idempotency_key("reward", rkey),
                payload={
                    "allocation_id": str(allocation.id),
                    "reward_key": rkey,
                    "quest_ref": quest_ref(quest.id),
                    "user_ref": user_ref(user.chain_user_ref),
                    "rank": rank,
                    "amount": amount,
                    "token_id": 0,
                },
                status="pending",
            )
        )
        await self.session.flush()
        from app.core import metrics

        metrics.incr("reward_allocations_total", reward_type="quest_rank")
        log.info(
            "reward_allocated",
            reward_key=rkey,
            user_id=str(user.id),
            rank=rank,
            amount=amount,
        )
        return allocation

    async def allocate_task_reward(
        self, *, user: User, task_id: uuid.UUID, amount: int, rkey: str
    ) -> RewardAllocation:
        existing = (
            await self.session.execute(
                select(RewardAllocation).where(RewardAllocation.reward_key == rkey)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        allocation = RewardAllocation(
            reward_key=rkey,
            user_id=user.id,
            task_id=task_id,
            reward_type="task",
            token_id=0,
            amount=amount,
            status="pending",
        )
        self.session.add(allocation)
        await self.session.flush()
        entry = await self.credit(
            user=user,
            amount=amount,
            reference_type="task",
            reference_id=str(allocation.id),
            reward_key_value=rkey,
            token_id=0,
            description=f"Task completion reward ({task_id})",
        )
        allocation.ledger_entry_id = entry.id
        self.session.add(
            TransactionOutbox(
                topic="reward",
                idempotency_key=tx_idempotency_key("reward", rkey),
                payload={
                    "allocation_id": str(allocation.id),
                    "reward_key": rkey,
                    "user_ref": user_ref(user.chain_user_ref),
                    "rank": 0,
                    "amount": amount,
                    "token_id": 0,
                },
                status="pending",
            )
        )
        await self.session.flush()
        return allocation

    async def admin_adjust(
        self,
        *,
        user: User,
        amount: int,
        adjust_key: str,
        reason: str,
    ) -> WalletLedgerEntry | None:
        """Manually adjust a user's OPT balance (audited, idempotent).

        ``amount`` may be positive (grant) or negative (claw back, floored so a
        debit cannot push below the current balance). Idempotent on
        ``adjust_key`` via the ledger's (reference_type, reference_id, entry_type)
        uniqueness, so an accidental double-submit never double-adjusts.
        """
        if amount == 0:
            return None
        account = await self.get_or_create_account(user.id)
        entry_type = "credit" if amount > 0 else "debit"
        magnitude = abs(amount)
        if entry_type == "debit" and account.cached_balance < magnitude:
            raise ConflictError("Adjustment exceeds the user's balance")
        new_balance = (
            account.cached_balance + magnitude
            if entry_type == "credit"
            else account.cached_balance - magnitude
        )
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type=entry_type,
            amount=magnitude,
            balance_after=new_balance,
            reference_type="admin_adjustment",
            reference_id=adjust_key,
            reward_key=adjust_key,
            description=f"Admin adjustment: {reason}"[:255],
        )
        try:
            async with self.session.begin_nested():
                self.session.add(entry)
                account.cached_balance = new_balance
                await self._apply_negative_policy(account, "admin_adjustment")
                await self.session.flush()
        except IntegrityError:
            # Another call with the same key already applied this adjustment.
            return (
                await self.session.execute(
                    select(WalletLedgerEntry).where(
                        WalletLedgerEntry.reference_type == "admin_adjustment",
                        WalletLedgerEntry.reference_id == adjust_key,
                    )
                )
            ).scalar_one_or_none()
        return entry

    async def allocate_event_reward(
        self,
        *,
        user: User,
        amount: int,
        reward_type: str,
        rkey: str,
        description: str,
    ) -> RewardAllocation | None:
        """Pay a one-off, idempotent OPT reward for a milestone event.

        Used for exam-perfect, quiz-master and course-completion payouts. The
        deterministic ``rkey`` guarantees at most one allocation per event, so
        re-grading or re-issuing a certificate never double-pays.
        """
        if amount <= 0:
            return None
        existing = (
            await self.session.execute(
                select(RewardAllocation).where(RewardAllocation.reward_key == rkey)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        allocation = RewardAllocation(
            reward_key=rkey,
            user_id=user.id,
            reward_type=reward_type,
            token_id=0,
            amount=amount,
            status="pending",
        )
        self.session.add(allocation)
        await self.session.flush()
        entry = await self.credit(
            user=user,
            amount=amount,
            reference_type="reward",
            reference_id=str(allocation.id),
            reward_key_value=rkey,
            token_id=0,
            description=description,
        )
        allocation.ledger_entry_id = entry.id
        self.session.add(
            TransactionOutbox(
                topic="reward",
                idempotency_key=tx_idempotency_key("reward", rkey),
                payload={
                    "allocation_id": str(allocation.id),
                    "reward_key": rkey,
                    "user_ref": user_ref(user.chain_user_ref),
                    "rank": 0,
                    "amount": amount,
                    "token_id": 0,
                },
                status="pending",
            )
        )
        await self.session.flush()
        from app.core import metrics

        metrics.incr("reward_allocations_total", reward_type=reward_type)
        log.info("reward_allocated", reward_key=rkey, user_id=str(user.id), amount=amount)
        return allocation

    async def debit_for_withdrawal(
        self, *, user: User, amount: int, withdrawal_id: uuid.UUID, destination: str
    ) -> WalletLedgerEntry:
        account = await self.get_or_create_account(user.id)
        if account.is_frozen:
            raise ConflictError("Wallet is frozen")
        if account.cached_balance < amount:
            raise ConflictError("Insufficient balance")

        new_balance = account.cached_balance - amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="debit",
            amount=amount,
            balance_after=new_balance,
            reference_type="withdrawal",
            reference_id=str(withdrawal_id),
            description=f"Withdrawal to {destination}",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self.session.flush()
        return entry

    async def debit_for_transfer(
        self, *, user: User, amount: int, reference_id: str, description: str | None = None
    ) -> WalletLedgerEntry:
        """Debit a user's balance for an internal transfer out (idempotent).

        ``reference_id`` is the transfer's unique reference, so a retry with the
        same id never double-debits. Keeps every balance mutation inside
        RewardEngine (no ad-hoc ledger writes in routers).
        """
        account = await self.get_or_create_account(user.id)
        if account.is_frozen:
            raise ConflictError("Wallet is frozen")
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "transfer_out",
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "debit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup
        if account.cached_balance < amount:
            raise ConflictError("Insufficient balance")
        new_balance = account.cached_balance - amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="debit",
            amount=amount,
            balance_after=new_balance,
            reference_type="transfer_out",
            reference_id=reference_id,
            description=description or "Internal transfer",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self.session.flush()
        return entry

    async def debit_withdrawal_fee(
        self, *, user_id: uuid.UUID, amount: int, withdrawal_id: uuid.UUID
    ) -> WalletLedgerEntry | None:
        """Debit a withdrawal fee as its own ledger entry (idempotent)."""
        if amount <= 0:
            return None
        account = await self.get_or_create_account(user_id)
        reference_id = str(withdrawal_id)
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "withdrawal_fee",
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "debit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup
        new_balance = account.cached_balance - amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="debit",
            amount=amount,
            balance_after=new_balance,
            reference_type="withdrawal_fee",
            reference_id=reference_id,
            description="Withdrawal fee",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self.session.flush()
        return entry

    async def refund_withdrawal_fee(
        self, *, user_id: uuid.UUID, amount: int, withdrawal_id: uuid.UUID
    ) -> WalletLedgerEntry | None:
        """Return a withdrawal fee (idempotent)."""
        if amount <= 0:
            return None
        account = await self.get_or_create_account(user_id)
        reference_id = str(withdrawal_id)
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "withdrawal_fee_refund",
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "credit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup
        new_balance = account.cached_balance + amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="credit",
            amount=amount,
            balance_after=new_balance,
            reference_type="withdrawal_fee_refund",
            reference_id=reference_id,
            description="Withdrawal fee refund",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self.session.flush()
        return entry

    async def balance(self, user_id: uuid.UUID) -> int:
        account = await self.get_or_create_account(user_id)
        return account.cached_balance

    # --- secondary assets (QTC / ORT) -------------------------------------
    async def asset_balance(self, user_id: uuid.UUID, asset: str) -> int:
        """Cached balance of a secondary asset (QTC/ORT); 0 if never held."""
        row = (
            await self.session.execute(
                select(WalletAssetBalance).where(
                    WalletAssetBalance.user_id == user_id,
                    WalletAssetBalance.asset == asset.upper(),
                )
            )
        ).scalar_one_or_none()
        return row.cached_balance if row is not None else 0

    async def _locked_asset_row(self, user_id: uuid.UUID, asset: str) -> WalletAssetBalance:
        asset = asset.upper()
        row = (
            await self.session.execute(
                select(WalletAssetBalance)
                .where(
                    WalletAssetBalance.user_id == user_id,
                    WalletAssetBalance.asset == asset,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            row = WalletAssetBalance(user_id=user_id, asset=asset, cached_balance=0)
            try:
                async with self.session.begin_nested():
                    self.session.add(row)
                    await self.session.flush()
            except IntegrityError:
                row = (
                    await self.session.execute(
                        select(WalletAssetBalance)
                        .where(
                            WalletAssetBalance.user_id == user_id,
                            WalletAssetBalance.asset == asset,
                        )
                        .with_for_update()
                    )
                ).scalar_one()
        return row

    async def credit_asset(self, *, user_id: uuid.UUID, asset: str, amount: int) -> int:
        """Add `amount` of a secondary asset; returns the new balance."""
        if amount <= 0:
            raise ConflictError("Amount must be positive")
        row = await self._locked_asset_row(user_id, asset)
        row.cached_balance += amount
        await self.session.flush()
        return row.cached_balance

    async def debit_asset(self, *, user_id: uuid.UUID, asset: str, amount: int) -> int:
        """Remove `amount` of a secondary asset; returns the new balance.

        A PL/pgSQL-free atomic guard: we lock the row then check sufficiency so
        two concurrent debits cannot both pass a stale read.
        """
        if amount <= 0:
            raise ConflictError("Amount must be positive")
        row = await self._locked_asset_row(user_id, asset)
        if row.cached_balance < amount:
            raise ConflictError(f"Insufficient {asset.upper()} balance")
        row.cached_balance -= amount
        await self.session.flush()
        return row.cached_balance

    async def reconcile(self, user_id: uuid.UUID) -> tuple[int, int]:
        """Return (cached_balance, computed_balance) for audit."""
        account = await self.get_or_create_account(user_id)
        from sqlalchemy import func

        credits = (
            await self.session.execute(
                select(func.coalesce(func.sum(WalletLedgerEntry.amount), 0)).where(
                    WalletLedgerEntry.account_id == account.id,
                    WalletLedgerEntry.entry_type == "credit",
                )
            )
        ).scalar_one()
        debits = (
            await self.session.execute(
                select(func.coalesce(func.sum(WalletLedgerEntry.amount), 0)).where(
                    WalletLedgerEntry.account_id == account.id,
                    WalletLedgerEntry.entry_type == "debit",
                )
            )
        ).scalar_one()
        return account.cached_balance, int(credits) - int(debits)

    async def reconcile_all(self, *, limit: int = 200) -> list[dict]:
        """Scan every OPT account for cached-vs-ledger drift and repair it.

        The ledger is the source of truth: ``cached_balance`` must equal
        ``sum(credits) - sum(debits)``. Any mismatch is reported (metric + row
        metadata), and the cached value is repaired to match the ledger so
        subsequent balance reads are correct again.
        """
        from sqlalchemy import func

        from app.core import metrics
        from app.models.identity import User

        accounts = (
            await self.session.execute(
                select(WalletAccount).order_by(WalletAccount.created_at).limit(limit)
            )
        ).scalars().all()
        drifted: list[dict] = []
        for account in accounts:
            credits = (
                await self.session.execute(
                    select(func.coalesce(func.sum(WalletLedgerEntry.amount), 0)).where(
                        WalletLedgerEntry.account_id == account.id,
                        WalletLedgerEntry.entry_type == "credit",
                    )
                )
            ).scalar_one()
            debits = (
                await self.session.execute(
                    select(func.coalesce(func.sum(WalletLedgerEntry.amount), 0)).where(
                        WalletLedgerEntry.account_id == account.id,
                        WalletLedgerEntry.entry_type == "debit",
                    )
                )
            ).scalar_one()
            expected = int(credits) - int(debits)
            if account.cached_balance != expected:
                drifted.append(
                    {
                        "account_id": str(account.id),
                        "user_id": str(account.user_id),
                        "cached": account.cached_balance,
                        "expected": expected,
                    }
                )
                account.cached_balance = expected
                metrics.incr("ledger_reconciliation_errors_total")
                log.warning(
                    "ledger_drift_detected",
                    account_id=str(account.id),
                    cached=drifted[-1]["cached"],
                    expected=expected,
                )
        if drifted:
            await self.session.flush()
        # Attach a user email-ish label for the admin view (id only, no PII leak).
        for row in drifted:
            user = await self.session.get(User, uuid.UUID(row["user_id"]))
            row["user_ref"] = user.chain_user_ref[:12] if user else None
        return drifted

    # --- secondary assets (QTC / ORT) -------------------------------------

    async def refund_reward(
        self, *, user_id: uuid.UUID, amount: int, allocation_id: uuid.UUID
    ) -> WalletLedgerEntry | None:
        """Reverse a reward credit whose on-chain mint failed/reverted.

        Idempotent on the allocation id. The reversal records the true balance
        (which may go negative if the user already spent the credit) so the
        double-entry invariant ``credit - debit == cached_balance`` — used by
        ``reconcile()`` — is preserved. Flooring at 0 previously created a
        phantom mismatch.
        """
        account = await self.get_or_create_account(user_id)
        reference_id = str(allocation_id)
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "reward_refund",
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "debit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup

        new_balance = account.cached_balance - amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="debit",
            amount=amount,
            balance_after=new_balance,
            reference_type="reward_refund",
            reference_id=reference_id,
            description="Reversal for failed on-chain reward",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self._apply_negative_policy(account, "reward_refund")
        await self.session.flush()
        return entry

    async def _apply_negative_policy(self, account: WalletAccount, reason: str) -> None:
        """Enforce the explicit negative-balance policy after a mutation.

        A negative OPT balance is *allowed* (it is the honest record of a
        clawback the user already spent) but it is never silent: we flag the
        account and bump ``ledger_negative_balance_total`` so operators can see
        it. When the balance climbs back to >= 0 the flag clears. Secondary
        assets (QTC/ORT) are never allowed to go negative — enforced by a DB
        CHECK constraint and by ``debit_asset``'s sufficiency guard.
        """
        from app.core import metrics

        if account.cached_balance < 0:
            account.is_in_debt = True
            metrics.incr("ledger_negative_balance_total", reason=reason)
            log.warning(
                "ledger_negative_balance",
                account_id=str(account.id),
                balance=account.cached_balance,
                reason=reason,
            )
        elif account.is_in_debt:
            account.is_in_debt = False

    async def refund_withdrawal(
        self, *, user_id: uuid.UUID, amount: int, withdrawal_id: uuid.UUID
    ) -> WalletLedgerEntry | None:
        """Reverse a withdrawal debit whose on-chain payout failed/reverted."""
        account = await self.get_or_create_account(user_id)
        reference_id = str(withdrawal_id)
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "withdrawal_refund",
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "credit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup

        new_balance = account.cached_balance + amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="credit",
            amount=amount,
            balance_after=new_balance,
            reference_type="withdrawal_refund",
            reference_id=reference_id,
            description="Reversal for failed on-chain withdrawal",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self.session.flush()
        return entry

    async def recredit_reward_retry(
        self, *, user_id: uuid.UUID, amount: int, allocation_id: uuid.UUID
    ) -> WalletLedgerEntry | None:
        """Restore a reward's credit when a previously-failed mint is retried.

        A failed/reverted reward was refunded (a ``reward_refund`` debit). If an
        admin retries it and the retry succeeds, the user must be credited again
        or the double-entry invariant (credit - debit == cached_balance) breaks.
        Idempotent on the allocation id.
        """
        account = await self.get_or_create_account(user_id)
        reference_id = str(allocation_id)
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "reward_retry",
                    WalletLedgerEntry.reference_id == reference_id,
                    WalletLedgerEntry.entry_type == "credit",
                )
            )
        ).scalar_one_or_none()
        if dup is not None:
            return dup
        new_balance = account.cached_balance + amount
        entry = WalletLedgerEntry(
            account_id=account.id,
            token_id=account.token_id,
            entry_type="credit",
            amount=amount,
            balance_after=new_balance,
            reference_type="reward_retry",
            reference_id=reference_id,
            description="Re-credit for retried on-chain reward",
        )
        self.session.add(entry)
        account.cached_balance = new_balance
        await self.session.flush()
        return entry

    async def refund_swap(
        self,
        *,
        user_id: uuid.UUID,
        opt_cost: int,
        asset: str,
        asset_amount: int,
        swap_key: str,
    ) -> None:
        """Reverse a swap whose on-chain routing failed/reverted.

        A successful swap debits ``opt_cost`` OPT and credits ``asset_amount``
        of the target asset. A failure must return the OPT *and* claw back the
        credited target asset so the ledger and on-chain balances stay in step.
        Idempotent on ``swap_key`` (the outbox idempotency key).
        """
        # Return the OPT (idempotent on swap_key).
        account = await self.get_or_create_account(user_id)
        dup = (
            await self.session.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "swap_refund",
                    WalletLedgerEntry.reference_id == swap_key,
                    WalletLedgerEntry.entry_type == "credit",
                )
            )
        ).scalar_one_or_none()
        # Already refunded: nothing to do (the target-asset claw-back below must
        # not run twice).
        if dup is not None:
            return
        if opt_cost > 0:
            new_balance = account.cached_balance + opt_cost
            self.session.add(
                WalletLedgerEntry(
                    account_id=account.id,
                    token_id=account.token_id,
                    entry_type="credit",
                    amount=opt_cost,
                    balance_after=new_balance,
                    reference_type="swap_refund",
                    reference_id=swap_key,
                    description=f"Reversal for failed swap to {asset}",
                )
            )
            account.cached_balance = new_balance
            await self.session.flush()
        # Claw back the credited target asset (best-effort: clamp at 0). Only
        # reached on the first (idempotent) refund for this swap_key.
        if asset and asset_amount > 0:
            row = await self._locked_asset_row(user_id, asset)
            row.cached_balance = max(0, row.cached_balance - asset_amount)
            await self.session.flush()

    async def refund_ai_request(
        self, *, user_id: uuid.UUID, requests: int, asset: str = "ORT"
    ) -> None:
        """Return ORT debited for AI usage whose on-chain burn failed/reverted.

        Idempotency is enforced at the caller (the outbox row is terminal), so a
        single refund is applied per failed item.
        """
        if requests <= 0:
            return
        row = await self._locked_asset_row(user_id, asset)
        row.cached_balance += requests
        await self.session.flush()
