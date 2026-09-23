"""Wallet & blockchain models.

Double-entry ledger (fixes the single `users.balance` anti-pattern):
  credit - debit = available balance.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, utcnow


class WalletAccount(Base, TimestampMixin):
    __tablename__ = "wallet_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    token_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Cached balance in integer token units; the ledger remains the source of truth.
    cached_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cached_pending: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    withdrawal_address: Mapped[str | None] = mapped_column(String(42))
    is_frozen: Mapped[bool] = mapped_column(default=False, nullable=False)
    # True when a compensation (e.g. a failed on-chain reward refund) drove the
    # cached balance negative — the user owes the platform. Surfaced to admins
    # and counted by the ledger_negative_balance_total metric.
    is_in_debt: Mapped[bool] = mapped_column(default=False, nullable=False)


class WalletAssetBalance(Base, TimestampMixin):
    """Per-user balance of a non-OPT QLoot asset (QTC / ORT).

    OPT (the base currency) is tracked by ``WalletAccount.cached_balance`` and
    the double-entry ledger. QTC/ORT are secondary assets obtained by swapping
    OPT through the OryphemProxy (ORX); their balances are cached here.
    """

    __tablename__ = "wallet_asset_balances"
    __table_args__ = (
        UniqueConstraint("user_id", "asset", name="uq_wallet_asset_user_asset"),
        # Secondary assets are never allowed to go negative (only OPT can, as a
        # clawback debt). A DB-level invariant so no code path can violate it.
        CheckConstraint("cached_balance >= 0", name="ck_wallet_asset_balance_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Asset key: "QTC" or "ORT".
    asset: Mapped[str] = mapped_column(String(8), nullable=False)
    cached_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class AiUsageCharge(Base):
    """One row per AI job that consumes ORT (or a free-tier slot).

    Makes metering idempotent and auditable: a job charges at most once
    (``charged`` set) and refunds at most once (``refunded`` set), no matter how
    often the worker retries. Also backs the "free AI requests remaining" query.
    """

    __tablename__ = "ai_usage_charges"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_ai_usage_job"),
        Index("ix_ai_usage_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    charged: Mapped[bool] = mapped_column(default=False, nullable=False)
    refunded: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class WalletLedgerEntry(Base):
    """Append-only double-entry rows. Never UPDATE; only INSERT."""

    __tablename__ = "wallet_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "reference_type",
            "reference_id",
            "entry_type",
            name="uq_ledger_reference_entry",
        ),
        Index("ix_ledger_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("wallet_accounts.id", ondelete="CASCADE"), nullable=False
    )
    token_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)  # credit|debit
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # always positive
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # reward|task|withdrawal...
    reference_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reward_key: Mapped[str | None] = mapped_column(String(66), index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class RewardAllocation(Base, TimestampMixin):
    """A reward owed to a user, tied to an on-chain event + tx."""

    __tablename__ = "reward_allocations"
    __table_args__ = (
        UniqueConstraint("reward_key", name="uq_reward_allocations_reward_key"),
        UniqueConstraint("quest_id", "user_id", "reward_type", name="uq_reward_quest_user_type"),
        Index("ix_reward_allocations_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reward_key: Mapped[str] = mapped_column(String(66), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    quest_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quests.id", ondelete="SET NULL")
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    reward_type: Mapped[str] = mapped_column(String(32), default="quest_rank", nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    token_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    ledger_entry_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    blockchain_transaction_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BlockchainTransaction(Base, TimestampMixin):
    __tablename__ = "blockchain_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_blockchain_transactions_idem"),
        Index("ix_blockchain_transactions_status", "status"),
        Index("ix_blockchain_transactions_hash", "transaction_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    idempotency_key: Mapped[str] = mapped_column(String(66), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    from_address: Mapped[str] = mapped_column(String(42), nullable=False)
    to_address: Mapped[str | None] = mapped_column(String(42))
    contract_address: Mapped[str | None] = mapped_column(String(42))
    nonce: Mapped[int | None] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_hash: Mapped[str | None] = mapped_column(String(66))
    arguments: Mapped[dict | None] = mapped_column(JSONB)
    transaction_hash: Mapped[str | None] = mapped_column(String(66))
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    confirmation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gas_limit: Mapped[int | None] = mapped_column(BigInteger)
    gas_used: Mapped[int | None] = mapped_column(BigInteger)
    effective_gas_price: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="created", nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BlockchainEvent(Base):
    __tablename__ = "blockchain_events"
    __table_args__ = (
        UniqueConstraint("transaction_hash", "log_index", name="uq_blockchain_events_tx_log"),
        Index("ix_blockchain_events_event_name", "event_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contract_address: Mapped[str] = mapped_column(String(42), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    log_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    args: Mapped[dict | None] = mapped_column(JSONB)
    processed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class ContractDeployment(Base, TimestampMixin):
    __tablename__ = "contract_deployments"
    __table_args__ = (
        UniqueConstraint("network", "address", name="uq_contract_deployments_net_addr"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str] = mapped_column(String(42), nullable=False)
    deployer: Mapped[str | None] = mapped_column(String(42))
    treasury: Mapped[str | None] = mapped_column(String(42))
    tx_hash: Mapped[str | None] = mapped_column(String(66))
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    abi: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class WithdrawalRequest(Base, TimestampMixin):
    __tablename__ = "withdrawal_requests"
    __table_args__ = (
        UniqueConstraint("reward_key", name="uq_withdrawal_requests_reward_key"),
        Index("ix_withdrawal_requests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reward_key: Mapped[str] = mapped_column(String(66), nullable=False)
    destination_address: Mapped[str] = mapped_column(String(42), nullable=False)
    token_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Fee charged on top of (and debited separately from) the withdrawn amount.
    fee_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="requested", nullable=False)
    blockchain_transaction_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(String(255))


class TransactionOutbox(Base):
    """Transactional outbox: written in the same tx as the business change."""

    __tablename__ = "transaction_outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transaction_outbox_idem"),
        Index("ix_transaction_outbox_status_available", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic: Mapped[str] = mapped_column(String(32), nullable=False)  # reward|withdrawal|pause...
    idempotency_key: Mapped[str] = mapped_column(String(66), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
