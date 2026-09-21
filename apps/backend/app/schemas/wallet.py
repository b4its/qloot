"""Wallet schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class WalletOut(BaseModel):
    user_id: uuid.UUID
    token_id: int
    available: int
    pending: int
    withdrawal_address: str | None
    # The single shared custodial wallet that holds all pooled OPC on-chain.
    # A user's own balance (``available``) is their focused share of it, tracked
    # per-user in the double-entry ledger.
    custodial_address: str | None = None
    network: str | None = None


class LedgerEntryOut(ORMModel):
    id: uuid.UUID
    entry_type: str
    amount: int
    balance_after: int
    reference_type: str
    reference_id: str
    description: str | None
    created_at: datetime


class RewardOut(BaseModel):
    id: uuid.UUID
    reward_key: str
    reward_type: str
    rank: int | None
    amount: int
    status: str
    quest_id: uuid.UUID | None
    task_id: uuid.UUID | None
    created_at: datetime


class TransferRequest(BaseModel):
    to_user_id: uuid.UUID
    amount: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=255)


class WalletAddressUpdate(BaseModel):
    """Set the caller's personal wallet address.

    ``source`` is provenance only ("manual" paste or "metamask" connect); the
    address itself is validated/normalised server-side.
    """

    address: str = Field(min_length=42, max_length=42)
    source: str = Field(default="manual", pattern="^(manual|metamask)$")


class WithdrawalRequestIn(BaseModel):
    amount: int = Field(gt=0)
    destination_address: str = Field(min_length=42, max_length=42)

    @field_validator("destination_address")
    @classmethod
    def _check_addr(cls, v: str) -> str:
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Invalid EVM address")
        return v.lower()


class WithdrawalOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    destination_address: str
    token_id: int
    amount: int
    status: str
    created_at: datetime
