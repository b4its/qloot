"""Blockchain client for the QLoot digital assets.

QLoot ships FOUR separate ERC-1155 UUPS contracts (see ``config``):
  OPT = OryphemToken (base currency)   QTC = QlootChain (capped 1e15)
  ORT = OryphemIntelligence (AI credit)  ORX = OryphemProxy (router)

Two modes:
  - dry_run=True (default in dev): an in-process fake chain that returns
    deterministic pseudo-hashes so the whole pipeline is exercisable offline.
  - dry_run=False: real web3.py against the configured RPC + contracts.

The private key is read from settings and never logged.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.errors import ChainError
from app.core.logging import get_logger

log = get_logger("chain")

# Minimal ABI shared by the three ERC-1155 assets (OPT/QTC/ORT). Each asset is
# its own contract and uses token id 0.
ASSET_ABI_MIN = [
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "bytes32", "name": "reason", "type": "bytes32"},
            {"internalType": "uint256", "name": "idempotencyKey", "type": "uint256"},
        ],
        "name": "rewardUser",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "burn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "pause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "unpause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "id", "type": "uint256"}],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalMinted",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalBurned",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "maxSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# Minimal ABI of the OryphemProxy (ORX) router.
ORX_ABI_MIN = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "assetId", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "swapOptFor",
        "outputs": [{"internalType": "uint256", "name": "optCost", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "requests", "type": "uint256"}],
        "name": "payAiRequest",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "proxyRates",
        "outputs": [
            {"internalType": "uint256", "name": "optPerOrt", "type": "uint256"},
            {"internalType": "uint256", "name": "optPerQtc", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Asset id used by the ORX router for each asset.
ORX_ASSET_IDS = {"QTC": 1, "ORT": 2}


@dataclass
class TxReceipt:
    tx_hash: str
    status: int
    block_number: int | None = None
    gas_used: int | None = None
    dry_run: bool = True


class ChainClient:
    def __init__(self) -> None:
        # In dry-run mode when no OPT address is configured (legacy behaviour).
        self.dry_run = settings.blockchain_dry_run or not settings.asset_address("OPT")
        self._w3: Any = None
        self._assets: dict[str, Any] = {}
        self._orx: Any = None
        self._account: Any = None
        # Serialises nonce allocation + submission: web3.py's HTTP provider is
        # sync, and two concurrent submits that both read the "latest" nonce
        # would sign conflicting transactions (one gets dropped).
        self._nonce_lock = asyncio.Lock()
        if not self.dry_run:
            self._init_web3()

    def _init_web3(self) -> None:
        try:
            from eth_account import Account
            from web3 import Web3

            if not settings.blockchain_private_key:
                raise ChainError("BLOCKCHAIN_PRIVATE_KEY is not configured")
            self._w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
            self._account = Account.from_key(settings.blockchain_private_key)
            for key in ("OPT", "QTC", "ORT"):
                addr = settings.asset_address(key)
                if addr:
                    self._assets[key] = self._w3.eth.contract(
                        address=Web3.to_checksum_address(addr), abi=ASSET_ABI_MIN
                    )
            orx_addr = settings.asset_address("ORX")
            if orx_addr:
                self._orx = self._w3.eth.contract(
                    address=Web3.to_checksum_address(orx_addr), abi=ORX_ABI_MIN
                )
        except ChainError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ChainError("Failed to initialise web3 client") from exc

    def _asset(self, key: str) -> Any:
        contract = self._assets.get(key.upper())
        if contract is None:
            raise ChainError(f"{key.upper()}_CONTRACT_ADDRESS is not configured")
        return contract

    @property
    def operator_address(self) -> str:
        """Address the backend signs with (in dry-run: the treasury).

        In the custodial model the operator account holds the pooled tokens, so
        withdrawals burn from here (burning from treasury would revert unless
        the operator is approved).
        """
        if self._account is not None:
            return self._account.address
        return settings.treasury_address or "0x" + "0" * 40

    def _fake_hash(self, *parts: str) -> str:
        return "0x" + hashlib.sha256("|".join(parts).encode()).hexdigest()

    async def reward_user(
        self,
        *,
        reward_key: str,
        user_ref: str,
        amount: int,
        reason: str = "reward",
        to: str | None = None,
        asset: str = "OPT",
    ) -> TxReceipt:
        """Pay an idempotent asset reward via the `rewardUser` function.

        The contract keys idempotency on a uint256; we derive it deterministically
        from the off-chain `reward_key` so retries never double-pay.
        """
        asset = asset.upper()
        # Derive a stable uint256 key from the bytes32/hex reward key.
        idem = int(reward_key, 16) if reward_key.startswith("0x") else _stable_uint(reward_key)
        idem &= (1 << 256) - 1

        if self.dry_run:
            tx_hash = self._fake_hash("reward", asset, reward_key, user_ref, str(amount))
            log.info("dry_run_reward_user", asset=asset, reward_key=reward_key, amount=amount)
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)

        assert self._account is not None and self._w3 is not None
        recipient = to or settings.treasury_address
        if not recipient:
            raise ChainError("TREASURY_ADDRESS is not configured")
        fn = self._asset(asset).functions.rewardUser(
            self._w3.to_checksum_address(recipient),
            int(amount),
            _b32(reason),
            idem,
        )
        return await self._send(fn)

    async def mint(self, *, to: str, amount: int, asset: str = "OPT") -> TxReceipt:
        """Mint `amount` of an asset to `to` (MINTER_ROLE)."""
        asset = asset.upper()
        if self.dry_run:
            return TxReceipt(
                tx_hash=self._fake_hash("mint", asset, to, str(amount)), status=1, dry_run=True
            )
        assert self._w3 is not None
        fn = self._asset(asset).functions.mint(self._w3.to_checksum_address(to), int(amount))
        return await self._send(fn)

    async def burn(self, *, from_: str, amount: int, asset: str = "OPT") -> TxReceipt:
        """Burn `amount` of an asset from `from_` (router/self burn)."""
        asset = asset.upper()
        if self.dry_run:
            return TxReceipt(
                tx_hash=self._fake_hash("burn", asset, from_, str(amount)), status=1, dry_run=True
            )
        assert self._w3 is not None
        fn = self._asset(asset).functions.burn(self._w3.to_checksum_address(from_), int(amount))
        return await self._send(fn)

    async def pause(self, asset: str = "OPT") -> TxReceipt:
        """Pause an asset (PAUSER_ROLE)."""
        asset = asset.upper()
        if self.dry_run:
            return TxReceipt(tx_hash=self._fake_hash("pause", asset), status=1, dry_run=True)
        return await self._send(self._asset(asset).functions.pause())

    async def unpause(self, asset: str = "OPT") -> TxReceipt:
        """Unpause an asset (PAUSER_ROLE)."""
        asset = asset.upper()
        if self.dry_run:
            return TxReceipt(tx_hash=self._fake_hash("unpause", asset), status=1, dry_run=True)
        return await self._send(self._asset(asset).functions.unpause())

    async def swap_opt_for(self, *, asset: str, amount: int) -> TxReceipt:
        """Route OPT into QTC/ORT through the ORX proxy (owner call)."""
        asset = asset.upper()
        if asset not in ORX_ASSET_IDS:
            raise ChainError("ORX swap asset must be QTC or ORT")
        if self.dry_run:
            return TxReceipt(
                tx_hash=self._fake_hash("swap", asset, str(amount)), status=1, dry_run=True
            )
        if self._orx is None:
            raise ChainError("ORX_CONTRACT_ADDRESS is not configured")
        fn = self._orx.functions.swapOptFor(ORX_ASSET_IDS[asset], int(amount))
        return await self._send(fn)

    async def pay_ai_request(self, *, requests: int) -> TxReceipt:
        """Burn ORT for AI usage (1 request = 1 ORT) via ORX."""
        if self.dry_run:
            return TxReceipt(
                tx_hash=self._fake_hash("ai_request", str(requests)), status=1, dry_run=True
            )
        if self._orx is None:
            raise ChainError("ORX_CONTRACT_ADDRESS is not configured")
        return await self._send(self._orx.functions.payAiRequest(int(requests)))

    async def anchor_document(self, *, anchor_key: str, document_hash: str) -> TxReceipt:
        """Anchor a document hash on QTC via the ORX router.

        ``anchor_key`` and ``document_hash`` are 0x-prefixed 32-byte values.
        Dry-run returns a deterministic hash so the flow is demoable offline.
        """
        if self.dry_run:
            return TxReceipt(
                tx_hash=self._fake_hash("anchor", anchor_key, document_hash),
                status=1,
                dry_run=True,
            )
        if self._orx is None:
            raise ChainError("ORX_CONTRACT_ADDRESS is not configured")
        return await self._send(
            self._orx.functions.anchorOnQtc(_b32(anchor_key), _b32(document_hash))
        )

    async def _send(self, fn, *, fee_bump_percent: int = 0) -> TxReceipt:
        assert self._w3 is not None and self._account is not None
        try:
            # Hold the lock across nonce read -> sign -> send so back-to-back
            # submissions cannot reuse the same nonce.
            async with self._nonce_lock:
                # "pending" counts transactions we already broadcast but that
                # are not yet mined; "latest" would return a stale nonce and
                # cause replacements/drops under rapid submission.
                nonce = self._w3.eth.get_transaction_count(self._account.address, "pending")
                tx = fn.build_transaction(
                    {
                        "from": self._account.address,
                        "nonce": nonce,
                        "chainId": settings.chain_id,
                        **self.estimate_fees(fee_bump_percent=fee_bump_percent),
                    }
                )
                signed = self._account.sign_transaction(tx)
                tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            return TxReceipt(
                tx_hash=tx_hash.hex(),
                status=0,
                dry_run=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise ChainError("Failed to submit transaction") from exc

    def estimate_fees(self, *, fee_bump_percent: int = 0) -> dict[str, int]:
        """Build EIP-1559 fee fields with a configurable buffer (WEB3-06).

        Estimates gas, the next base fee and a suggested priority fee, applies
        the configured buffers, and returns the ``gas``/``maxFeePerGas``/
        ``maxPriorityFeePerGas`` dict to merge into the transaction. A
        ``fee_bump_percent`` raises the max fee for a stuck-transaction
        resubmission.
        """
        assert self._w3 is not None
        sender = self._account.address if self._account is not None else None
        try:
            gas = int(self._w3.eth.estimate_gas({"from": sender} if sender else {}))
        except Exception:  # noqa: BLE001 - estimation can revert; fall back
            gas = 200_000
        try:
            base = int(self._w3.eth.get_block("latest").get("baseFeePerGas") or 0)
        except Exception:  # noqa: BLE001
            base = 0
        try:
            priority = int(
                self._w3.eth.max_priority_fee
                if hasattr(self._w3.eth, "max_priority_fee")
                else self._w3.to_wei(1, "gwei")
            )
        except Exception:  # noqa: BLE001
            priority = self._w3.to_wei(1, "gwei")

        priority = int(priority * settings.tx_priority_fee_buffer)
        # EIP-1559: max fee must cover base + tip with headroom for a few blocks.
        if base > 0:
            max_fee = int(base * settings.tx_base_fee_buffer + priority)
        else:
            # Chains without base fee (legacy): fall back to a legacy gas price.
            max_fee = priority
        if fee_bump_percent:
            bump = 1 + fee_bump_percent / 100.0
            priority = int(priority * bump)
            max_fee = int(max_fee * bump)
        return {
            "gas": max(gas, 21_000),
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority,
        }

    def get_confirmations(self, tx_hash: str) -> int:
        if self.dry_run:
            return settings.opc_confirmations
        assert self._w3 is not None
        try:
            receipt = self._w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None:
                return 0
            head = self._w3.eth.block_number
            return max(0, head - receipt["blockNumber"] + 1)
        except Exception:  # noqa: BLE001
            return 0

    def get_receipt(self, tx_hash: str) -> TxReceipt | None:
        if self.dry_run:
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)
        assert self._w3 is not None
        try:
            r = self._w3.eth.get_transaction_receipt(tx_hash)
            if r is None:
                return None
            return TxReceipt(
                tx_hash=tx_hash,
                status=int(r.get("status", 0)),
                block_number=r.get("blockNumber"),
                gas_used=r.get("gasUsed"),
                dry_run=False,
            )
        except Exception:  # noqa: BLE001
            return None

    def status(self) -> dict:
        """Public, address-free status (safe for any authenticated user)."""
        return {
            "dry_run": self.dry_run,
            "network": settings.blockchain_network,
            "chain_id": settings.chain_id,
            "token_id": settings.opc_token_id,
            "confirmations_required": settings.opc_confirmations,
        }

    def admin_status(self) -> dict:
        """Privileged status including every asset/router address (admin only)."""
        return {
            **self.status(),
            # Backwards-compatible single-contract fields = OPT.
            "contract_address": settings.asset_address("OPT") or None,
            "treasury_address": settings.treasury_address or None,
            # Full multi-contract map.
            "assets": {
                "OPT": {
                    "name": "OryphemToken",
                    "symbol": "OPT",
                    "address": settings.asset_address("OPT") or None,
                    "role": "base currency (unlimited)",
                },
                "QTC": {
                    "name": "QlootChain",
                    "symbol": "QTC",
                    "address": settings.asset_address("QTC") or None,
                    "role": "premium chain asset (cap 1e15)",
                },
                "ORT": {
                    "name": "OryphemIntelligence",
                    "symbol": "ORT",
                    "address": settings.asset_address("ORT") or None,
                    "role": "AI credit (1 request = 1 ORT)",
                },
                "ORX": {
                    "name": "OryphemProxy",
                    "symbol": "ORX",
                    "address": settings.asset_address("ORX") or None,
                    "role": "router (1 ORT = 50 OPT, 1 QTC = 1000 OPT)",
                },
            },
        }

    def explorer_url(self, tx_hash: str) -> str | None:
        if settings.chain_id == 11155111:
            return f"https://sepolia.etherscan.io/tx/{tx_hash}"
        return None


def _b32(value: str) -> bytes:
    """Encode a value as bytes32.

    Accepts a 0x-prefixed 32-byte hex string as-is; otherwise keccak256-hashes
    the UTF-8 string (so reasons like "reward" map to a stable bytes32).
    """
    if value.startswith("0x") and len(value) == 66:
        try:
            return bytes.fromhex(value[2:])
        except ValueError:
            pass
    return bytes.fromhex(_stable_uint(value).to_bytes(32, "big").hex())


def _stable_uint(value: str) -> int:
    """Deterministically map an arbitrary string to a uint256 integer."""
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest(), "big")


_client: ChainClient | None = None


def get_chain_client() -> ChainClient:
    global _client
    if _client is None:
        _client = ChainClient()
    return _client
