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

from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.models.identity import User
from app.models.quest import Quest
from app.models.wallet import (
    RewardAllocation,
    TransactionOutbox,
    WalletAccount,
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

    async def balance(self, user_id: uuid.UUID) -> int:
        account = await self.get_or_create_account(user_id)
        return account.cached_balance

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
        await self.session.flush()
        return entry

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
