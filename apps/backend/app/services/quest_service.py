"""Quest service with deterministic fastest-valid winner selection (§13).

Winner ordering (all server-authoritative):
  1. Quest is open at submission time.
  2. Attempt was valid (submitted before deadline, not flagged).
  3. Score >= min passing score for that rank.
  4. Past `submitted_at` (server time) — NOT `graded_at`.
  Tie-breakers: higher score, then shorter duration, then lower attempt id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.models.quest import Quest, QuestAttempt, QuestRule, QuestWinner
from app.services.keys import reward_key

log = get_logger("quests")


class QuestService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, owner: User, rules: list[dict], **data) -> Quest:
        quest = Quest(owner_id=owner.id, **data)
        self.session.add(quest)
        await self.session.flush()
        if not rules:
            rules = [
                {"rank": i + 1, "reward_amount": amt}
                for i, amt in enumerate(settings.reward_ranks[: quest.top_n_winners])
            ]
        for r in rules:
            self.session.add(QuestRule(quest_id=quest.id, **r))
        await self.session.flush()
        return quest

    async def get(self, quest_id: uuid.UUID) -> Quest:
        quest = await self.session.get(Quest, quest_id)
        if quest is None:
            raise NotFoundError("Quest not found")
        return quest

    async def list_all(self, user: User, *, limit: int = 50, offset: int = 0) -> list[Quest]:
        stmt = select(Quest).order_by(Quest.created_at.desc()).limit(limit).offset(offset)
        if not user.has_role("teacher", "admin"):
            stmt = stmt.where(Quest.status.in_(("open", "finalized")))
        elif not user.has_role("admin"):
            stmt = stmt.where(Quest.owner_id == user.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_rules(self, quest_id: uuid.UUID) -> list[QuestRule]:
        stmt = select(QuestRule).where(QuestRule.quest_id == quest_id).order_by(QuestRule.rank)
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(self, quest_id: uuid.UUID, user: User, **data) -> Quest:
        quest = await self._owned(quest_id, user)
        for k, v in data.items():
            if v is not None:
                setattr(quest, k, v)
        await self.session.flush()
        return quest

    async def publish(self, quest_id: uuid.UUID, user: User) -> Quest:
        quest = await self._owned(quest_id, user)
        quest.status = "open"
        quest.opens_at = quest.opens_at or datetime.now(UTC)
        await self.session.flush()
        return quest

    async def record_attempt(
        self, quest_id: uuid.UUID, user: User, *, exam_attempt_id: uuid.UUID | None
    ) -> QuestAttempt:
        quest = await self.get(quest_id)
        now = datetime.now(UTC)
        existing = (
            await self.session.execute(
                select(QuestAttempt).where(
                    QuestAttempt.quest_id == quest_id, QuestAttempt.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            # First valid submission wins; do not overwrite.
            return existing

        # Deadline window is server-authoritative: a submission outside
        # [opens_at, closes_at] is recorded but marked invalid, so it can never
        # win. (The exam submit path still records so the attempt is auditable.)
        is_valid = True
        reason: str | None = None
        if quest.opens_at is not None and now < quest.opens_at:
            is_valid, reason = False, "submitted before quest opened"
        elif quest.closes_at is not None and now > quest.closes_at:
            is_valid, reason = False, "submitted after quest closed"

        attempt = QuestAttempt(
            quest_id=quest_id,
            user_id=user.id,
            exam_attempt_id=exam_attempt_id,
            submitted_at=now,
            is_valid=is_valid,
            invalid_reason=reason,
        )
        self.session.add(attempt)
        await self.session.flush()

        # Badge: completing the first quest (attempt recorded, any validity).
        from app.services.social_service import BadgeService

        await BadgeService(self.session).award(user=user, code="first_quest")
        return attempt

    async def finalize(self, quest_id: uuid.UUID, user: User) -> tuple[Quest, list[QuestWinner]]:
        quest = await self._owned(quest_id, user)
        if quest.status == "finalized":
            existing_winners = await self.list_winners(quest_id)
            return quest, existing_winners

        # Lock the quest row so only one finalize runs at a time.
        await self.session.execute(select(Quest.id).where(Quest.id == quest_id).with_for_update())

        rules = {r.rank: r for r in await self.list_rules(quest_id)}
        top_n = quest.top_n_winners or settings.default_top_n_winners

        # Deterministic ordering (matches the module docstring):
        #   higher score, then shorter duration, then lower attempt id.
        # Only valid, graded, non-flagged attempts inside the quest window.
        stmt = (
            select(QuestAttempt, ExamAttempt)
            .join(ExamAttempt, ExamAttempt.id == QuestAttempt.exam_attempt_id)
            .where(QuestAttempt.quest_id == quest_id, QuestAttempt.is_valid.is_(True))
            .where(ExamAttempt.status == "graded")
            .where(ExamAttempt.is_flagged.is_(False))
            .order_by(
                ExamAttempt.score_bp.desc().nullslast(),
                ExamAttempt.duration_seconds.asc().nullslast(),
                ExamAttempt.id.asc(),
            )
        )
        rows = (await self.session.execute(stmt)).all()

        # Existing winners (idempotent re-finalize) counted once.
        existing_by_user = {w.user_id: w for w in await self.list_winners(quest_id)}

        winners: list[QuestWinner] = []
        rank = 0
        for quest_attempt, exam_attempt in rows:
            if rank >= top_n:
                break
            next_rank = rank + 1
            rule = rules.get(next_rank)
            min_score = rule.min_score_bp if rule and rule.min_score_bp is not None else 0
            if exam_attempt.score_bp is None or exam_attempt.score_bp < min_score:
                continue

            already = existing_by_user.get(quest_attempt.user_id)
            if already is not None:
                # Already a winner: take the slot but do not re-insert.
                winners.append(already)
                rank = next_rank
                continue

            rkey = reward_key(quest_id, quest_attempt.user_id, next_rank, quest.reward_version)
            winner = QuestWinner(
                quest_id=quest_id,
                user_id=quest_attempt.user_id,
                rank=next_rank,
                score_bp=exam_attempt.score_bp,
                submitted_at=quest_attempt.submitted_at,
                duration_seconds=exam_attempt.duration_seconds,
                attempt_id=exam_attempt.id,
                reward_key=rkey,
            )
            self.session.add(winner)
            await self.session.flush()
            winners.append(winner)
            rank = next_rank

        quest.status = "finalized"
        quest.finalized_at = datetime.now(UTC)
        await self.session.flush()
        log.info("quest_finalized", quest_id=str(quest_id), winners=len(winners))
        return quest, winners

    async def list_winners(self, quest_id: uuid.UUID) -> list[QuestWinner]:
        stmt = (
            select(QuestWinner).where(QuestWinner.quest_id == quest_id).order_by(QuestWinner.rank)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _owned(self, quest_id: uuid.UUID, user: User) -> Quest:
        quest = await self.get(quest_id)
        if not user.has_role("admin") and quest.owner_id != user.id:
            raise ForbiddenError("You do not own this quest")
        return quest
