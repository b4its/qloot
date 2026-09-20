"""Deterministic identifiers for rewards (off-chain == on-chain keys)."""

from __future__ import annotations

import hashlib
import uuid


def _h(*parts: str) -> str:
    return "0x" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def reward_key(quest_id: uuid.UUID, user_id: uuid.UUID, rank: int, reward_version: int) -> str:
    """Idempotency key for a quest rank reward.

    Stable across retries so neither the DB nor the contract will double-pay.
    """
    return _h("reward", str(quest_id), str(user_id), str(rank), str(reward_version))


def task_reward_key(task_id: uuid.UUID, user_id: uuid.UUID, period: str = "") -> str:
    """Idempotency key for a task reward.

    ``period`` makes recurring tasks (e.g. daily) rewardable once per period
    while remaining stable within the period (so retries do not double-pay).
    """
    return _h("task", str(task_id), str(user_id), period)


def withdrawal_key(withdrawal_id: uuid.UUID) -> str:
    return _h("withdrawal", str(withdrawal_id))


def user_ref(chain_user_ref: str) -> str:
    """On-chain user reference is already an opaque salted hash."""
    return chain_user_ref


def quest_ref(quest_id: uuid.UUID) -> str:
    return _h("quest", str(quest_id))


def tx_idempotency_key(*parts: str) -> str:
    return _h("tx", *parts)
