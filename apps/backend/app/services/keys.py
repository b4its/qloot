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


def exam_reward_key(attempt_id: uuid.UUID, kind: str) -> str:
    """Idempotency key for an exam-derived reward.

    ``kind`` distinguishes perfect-exam from quiz-master (a single attempt can
    legitimately earn both), so each is paid at most once per attempt.
    """
    return _h("exam", str(attempt_id), kind)


def course_completion_key(course_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Idempotency key for a course-completion reward (once per course/user)."""
    return _h("course_complete", str(course_id), str(user_id))


def level_up_reward_key(user_id: uuid.UUID, level: int) -> str:
    """Idempotency key for a level-up bonus (once per user per level)."""
    return _h("level_up", str(user_id), str(level))


def certificate_anchor_key(certificate_id: uuid.UUID) -> str:
    """On-chain anchor key for a certificate (deterministic, one per cert)."""
    return _h("cert_anchor", str(certificate_id))


def withdrawal_key(withdrawal_id: uuid.UUID) -> str:
    return _h("withdrawal", str(withdrawal_id))


def user_ref(chain_user_ref: str) -> str:
    """On-chain user reference is already an opaque salted hash."""
    return chain_user_ref


def quest_ref(quest_id: uuid.UUID) -> str:
    return _h("quest", str(quest_id))


def tx_idempotency_key(*parts: str) -> str:
    return _h("tx", *parts)
