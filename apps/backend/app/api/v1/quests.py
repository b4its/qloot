"""Quest endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.db.session import transaction
from app.models.identity import User
from app.schemas.quest import (
    FinalizeResult,
    QuestCreate,
    QuestDetailOut,
    QuestOut,
    QuestRuleOut,
    QuestUpdate,
    WinnerOut,
)
from app.services.quest_service import QuestService
from app.services.realtime import event_bus
from app.services.reward_engine import RewardEngine
from app.services.social_service import BadgeService, NotificationService

router = APIRouter()


@router.get("", response_model=list[QuestOut])
async def list_quests(user: CurrentUser, db: DbSession, limit: int = 50, offset: int = 0):
    return await QuestService(db).list_all(user, limit=limit, offset=offset)


@router.post("", response_model=QuestOut, status_code=status.HTTP_201_CREATED)
async def create_quest(payload: QuestCreate, user: TeacherUser, db: DbSession):
    data = payload.model_dump()
    rules = data.pop("rules")
    async with transaction(db):
        return await QuestService(db).create(user, rules, **data)


@router.get("/{quest_id}", response_model=QuestDetailOut)
async def get_quest(quest_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = QuestService(db)
    quest = await service.get(quest_id)
    rules = await service.list_rules(quest_id)
    detail = QuestDetailOut.model_validate(quest)
    detail.rules = [QuestRuleOut.model_validate(r) for r in rules]
    return detail


@router.patch("/{quest_id}", response_model=QuestOut)
async def update_quest(quest_id: uuid.UUID, payload: QuestUpdate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await QuestService(db).update(
            quest_id, user, **payload.model_dump(exclude_unset=True)
        )


@router.post("/{quest_id}/publish", response_model=QuestOut)
async def publish_quest(quest_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await QuestService(db).publish(quest_id, user)


@router.post("/{quest_id}/finalize", response_model=FinalizeResult)
async def finalize_quest(quest_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        service = QuestService(db)
        quest, winners = await service.finalize(quest_id, user)
        rules = {r.rank: r for r in await service.list_rules(quest_id)}

        engine = RewardEngine(db)
        badges = BadgeService(db)
        notifications = NotificationService(db)
        created = 0
        out: list[WinnerOut] = []
        for w in winners:
            rule = rules.get(w.rank)
            amount = rule.reward_amount if rule else 0
            user_row = await db.get(User, w.user_id)
            if user_row is not None and amount > 0 and w.rank <= quest.top_n_winners:
                await engine.allocate_quest_reward(
                    quest=quest,
                    user=user_row,
                    rank=w.rank,
                    amount=amount,
                    score_bp=w.score_bp,
                )
                created += 1
                # Notify + award badges (idempotent).
                await notifications.notify(
                    user_id=user_row.id,
                    kind="reward",
                    title=f"You earned {amount} OPC!",
                    body=f"Quest '{quest.title}' — rank {w.rank}",
                    data={"quest_id": str(quest.id), "rank": w.rank, "amount": amount},
                )
                await badges.award(user=user_row, code="first_reward")
                if w.rank <= 3:
                    await badges.award(
                        user=user_row,
                        code="top_3",
                        meta={"quest_id": str(quest.id), "rank": w.rank},
                    )
            out.append(
                WinnerOut(
                    rank=w.rank,
                    user_id=w.user_id,
                    score_bp=w.score_bp,
                    submitted_at=w.submitted_at,
                    reward_key=w.reward_key,
                    reward_amount=amount,
                )
            )
    await event_bus.publish(f"quest:{quest_id}", {"type": "quest.finalized", "winners": len(out)})
    return FinalizeResult(quest_id=quest_id, winners=out, allocations_created=created)


@router.get("/{quest_id}/winners", response_model=list[WinnerOut])
async def list_winners(quest_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = QuestService(db)
    winners = await service.list_winners(quest_id)
    rules = {r.rank: r for r in await service.list_rules(quest_id)}
    return [
        WinnerOut(
            rank=w.rank,
            user_id=w.user_id,
            score_bp=w.score_bp,
            submitted_at=w.submitted_at,
            reward_key=w.reward_key,
            reward_amount=rules[w.rank].reward_amount if w.rank in rules else 0,
        )
        for w in winners
    ]
