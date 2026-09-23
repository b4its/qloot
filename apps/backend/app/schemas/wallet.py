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
    # The caller's *own* personal withdrawal wallet. The shared platform
    # (custodial) address is never exposed to users.
    withdrawal_address: str | None = None
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


class TransferRecipientOut(BaseModel):
    """A candidate recipient for an internal OPT transfer (directory entry).

    The raw email is never exposed — only a masked handle + display name so a
    user cannot enumerate every account's address.
    """

    user_id: uuid.UUID
    full_name: str
    email_masked: str
    handle: str


class WalletAddressUpdate(BaseModel):
    """Set the caller's personal wallet address.

    ``source`` is provenance only ("manual" paste or "metamask" connect); the
    address itself is validated/normalised server-side.
    """

    address: str = Field(min_length=42, max_length=42)
    source: str = Field(default="manual", pattern="^(manual|metamask)$")


class AssetBalanceOut(BaseModel):
    """A single QLoot asset balance for the caller."""

    asset: str  # OPT | QTC | ORT
    name: str
    symbol: str
    balance: int
    role: str


class WalletAssetsOut(BaseModel):
    user_id: uuid.UUID
    network: str | None = None
    assets: list[AssetBalanceOut]


class SwapRequestIn(BaseModel):
    """Convert OPT into QTC or ORT via the OryphemProxy (ORX)."""

    asset: str = Field(pattern="^(QTC|ORT)$")
    amount: int = Field(gt=0, description="Units of the target asset to receive")


class AIRequestIn(BaseModel):
    """Spend ORT on AI usage (1 request = 1 ORT)."""

    requests: int = Field(gt=0, le=1000)


class WithdrawalRequestIn(BaseModel):
    amount: int = Field(gt=0)
    destination_address: str = Field(min_length=42, max_length=42)

    @field_validator("destination_address")
    @classmethod
    def _check_addr(cls, v: str) -> str:
        # Use the same canonical validator as PATCH /wallet/address so a
        # malformed (non-hex) 42-char string can never be persisted as a
        # withdrawal destination. Returns the EIP-55 checksummed address.
        # ``validate_wallet_address`` raises the app's ``ValidationError`` (not a
        # pydantic ``ValueError``), so re-raise as ``ValueError`` for pydantic to
        # turn into a clean 422 instead of a 500.
        from app.core.errors import ValidationError as QLValidationError
        from app.services.wallet_service import validate_wallet_address

        try:
            return validate_wallet_address(v)
        except QLValidationError as exc:
            raise ValueError(str(exc.message)) from exc


class WithdrawalOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    destination_address: str
    token_id: int
    amount: int
    fee_amount: int = 0
    status: str
    created_at: datetime
    reviewed_at: datetime | None = None
    reject_reason: str | None = None
