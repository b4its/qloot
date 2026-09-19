"""Blockchain client: record rewards/withdrawals on the OPC ERC-1155.

Two modes:
  - dry_run=True (default in dev): an in-process fake chain that returns
    deterministic pseudo-hashes so the whole pipeline is exercisable offline.
  - dry_run=False: real web3.py against the configured RPC + contract.

The private key is read from settings and never logged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.core.errors import ChainError
from app.core.logging import get_logger

log = get_logger("chain")

OPC_ABI_MIN = [
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
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "addXp",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint8", "name": "badgeId", "type": "uint8"},
            {"internalType": "string", "name": "uri", "type": "string"},
            {"internalType": "bool", "name": "soulbound", "type": "bool"},
        ],
        "name": "registerBadge",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint8", "name": "badgeId", "type": "uint8"},
            {"internalType": "string", "name": "uri", "type": "string"},
        ],
        "name": "awardBadge",
        "outputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "courseId", "type": "uint256"},
            {"internalType": "uint256", "name": "rewardAmount", "type": "uint256"},
            {"internalType": "uint8", "name": "badgeId", "type": "uint8"},
            {"internalType": "bool", "name": "active", "type": "bool"},
        ],
        "name": "createCourse",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "withdrawalRef", "type": "bytes32"},
            {"internalType": "address", "name": "destination", "type": "address"},
            {"internalType": "uint256", "name": "tokenId", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "completeWithdrawal",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "totalSupply",
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
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "xp",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "level",
        "outputs": [{"internalType": "uint32", "name": "", "type": "uint32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "userBadgeCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


@dataclass
class TxReceipt:
    tx_hash: str
    status: int
    block_number: int | None = None
    gas_used: int | None = None
    dry_run: bool = True


class ChainClient:
    def __init__(self) -> None:
        self.dry_run = settings.blockchain_dry_run or not settings.opc_contract_address
        self._w3: Any = None
        self._contract: Any = None
        self._account: Any = None
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
            self._contract = self._w3.eth.contract(
                address=Web3.to_checksum_address(settings.opc_contract_address),
                abi=OPC_ABI_MIN,
            )
        except ChainError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ChainError("Failed to initialise web3 client") from exc

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
    ) -> TxReceipt:
        """Pay an idempotent OPC reward via the v2 `rewardUser` function.

        The contract keys idempotency on a uint256; we derive it deterministically
        from the off-chain `reward_key` so retries never double-pay.
        """
        # Derive a stable uint256 key from the bytes32/hex reward key.
        idem = int(reward_key, 16) if reward_key.startswith("0x") else _stable_uint(reward_key)
        idem &= (1 << 256) - 1

        if self.dry_run:
            tx_hash = self._fake_hash("reward", reward_key, user_ref, str(amount))
            log.info("dry_run_reward_user", reward_key=reward_key, amount=amount)
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)

        assert self._contract is not None and self._account is not None and self._w3 is not None
        recipient = to or settings.treasury_address
        if not recipient:
            raise ChainError("TREASURY_ADDRESS is not configured")
        fn = self._contract.functions.rewardUser(
            self._w3.to_checksum_address(recipient),
            int(amount),
            _b32(reason),
            idem,
        )
        return await self._send(fn)

    async def add_xp(self, *, to: str, amount: int, user_ref: str = "") -> TxReceipt:
        if self.dry_run:
            tx_hash = self._fake_hash("xp", user_ref or to, str(amount))
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)
        assert self._contract is not None and self._w3 is not None
        fn = self._contract.functions.addXp(self._w3.to_checksum_address(to), int(amount))
        return await self._send(fn)

    async def award_badge(self, *, to: str, badge_id: int, uri: str = "") -> TxReceipt:
        if self.dry_run:
            tx_hash = self._fake_hash("badge", to, str(badge_id))
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)
        assert self._contract is not None and self._w3 is not None
        fn = self._contract.functions.awardBadge(
            self._w3.to_checksum_address(to), int(badge_id), uri
        )
        return await self._send(fn)

    async def register_badge(
        self, *, badge_id: int, uri: str = "", soulbound: bool = False
    ) -> TxReceipt:
        if self.dry_run:
            tx_hash = self._fake_hash("badge_register", str(badge_id))
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)
        assert self._contract is not None
        fn = self._contract.functions.registerBadge(int(badge_id), uri, bool(soulbound))
        return await self._send(fn)

    async def complete_withdrawal(
        self, *, withdrawal_ref: str, destination: str, amount: int, token_id: int
    ) -> TxReceipt:
        if self.dry_run:
            tx_hash = self._fake_hash("withdrawal", withdrawal_ref, destination, str(amount))
            return TxReceipt(tx_hash=tx_hash, status=1, dry_run=True)
        assert self._contract is not None and self._w3 is not None
        fn = self._contract.functions.completeWithdrawal(
            _b32(withdrawal_ref),
            self._w3.to_checksum_address(destination),
            int(token_id),
            int(amount),
        )
        return await self._send(fn)

    async def _send(self, fn) -> TxReceipt:
        assert self._w3 is not None and self._account is not None
        try:
            nonce = self._w3.eth.get_transaction_count(self._account.address)
            tx = fn.build_transaction(
                {
                    "from": self._account.address,
                    "nonce": nonce,
                    "chainId": settings.chain_id,
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
        return {
            "dry_run": self.dry_run,
            "network": settings.blockchain_network,
            "chain_id": settings.chain_id,
            "contract_address": settings.opc_contract_address or None,
            "treasury_address": settings.treasury_address or None,
            "token_id": settings.opc_token_id,
            "confirmations_required": settings.opc_confirmations,
        }

    def explorer_url(self, tx_hash: str) -> str | None:
        if settings.chain_id == 11155111:
            return f"https://sepolia.etherscan.io/tx/{tx_hash}"
        return None


def _b32(hexstr: str) -> bytes:
    s = hexstr[2:] if hexstr.startswith("0x") else hexstr
    return bytes.fromhex(s.zfill(64))


def _stable_uint(value: str) -> int:
    """Deterministically map an arbitrary string to a uint256 integer."""
    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest(), "big")


_client: ChainClient | None = None


def get_chain_client() -> ChainClient:
    global _client
    if _client is None:
        _client = ChainClient()
    return _client
