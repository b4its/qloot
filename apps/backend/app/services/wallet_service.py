"""Personal wallet address helpers.

Every account has a *personal* wallet address (``WalletAccount.withdrawal_address``)
that OPT withdrawals are sent to. It defaults to ``settings.default_wallet_address``
and each user may change their own at any time — by pasting an address or by
connecting MetaMask in the browser (which just fills in the address).

The address is stored EIP-55 checksummed so the on-chain client can use it
without re-normalising.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ValidationError
from app.models.identity import User
from app.models.wallet import WalletAccount
from app.services.audit import record as audit_record


def default_wallet_address() -> str:
    """The address applied to accounts that never set one."""
    return (settings.default_wallet_address or "").strip()


def validate_wallet_address(value: str) -> str:
    """Return the EIP-55 checksummed address, or raise ``ValidationError``.

    Accepts any-case 0x-prefixed 20-byte address; rejects everything else.
    """
    raw = (value or "").strip()
    if len(raw) != 42 or not raw.startswith("0x"):
        raise ValidationError("Alamat wallet tidak valid (harus 0x + 40 hex)")
    try:
        from web3 import Web3

        return Web3.to_checksum_address(raw)
    except Exception as exc:  # noqa: BLE001 - any parse/checksum failure
        # Fall back to a strict hex check so a malformed address is rejected
        # even if web3 is unavailable.
        body = raw[2:]
        if len(body) == 40 and all(c in "0123456789abcdefABCDEF" for c in body):
            return "0x" + body.lower()
        raise ValidationError("Alamat wallet tidak valid") from exc


def effective_wallet_address(account: WalletAccount) -> str:
    """The address a user actually uses: their own, else the platform default."""
    return account.withdrawal_address or default_wallet_address() or ""


async def set_wallet_address(
    db: AsyncSession,
    user: User,
    address: str,
    *,
    source: str = "manual",
) -> WalletAccount:
    """Set the caller's personal wallet address (own account only).

    ``source`` records *how* it was chosen ("manual" paste or "metamask") in the
    audit log so the provenance of a change is traceable.
    """
    from app.services.reward_engine import RewardEngine

    checksummed = validate_wallet_address(address)
    account = await RewardEngine(db).get_or_create_account(user.id)
    previous = account.withdrawal_address
    account.withdrawal_address = checksummed
    audit_record(
        db,
        actor_id=user.id,
        action="wallet.address_change",
        entity_type="wallet_account",
        entity_id=str(account.id),
        data={"previous": previous, "new": checksummed, "source": source},
    )
    await db.flush()
    return account
