"""Quest endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.core.errors import ForbiddenError, NotFoundError
from app.db.session import transaction
from app.models.exam import Exam
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

router = APIRouter()


@router.get("", response_model=list[QuestOut])
async def list_quests(
    user: CurrentUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    return await QuestService(db).list_all(user, limit=limit, offset=offset)


@router.post("", response_model=QuestOut, status_code=status.HTTP_201_CREATED)
async def create_quest(payload: QuestCreate, user: TeacherUser, db: DbSession):
    data = payload.model_dump()
    rules = data.pop("rules")
    async with transaction(db):
        # A quest may only reference an exam the caller owns (or any, for an
        # admin) — otherwise a teacher could finalize rewards against someone
        # else's exam.
        exam_id = data.get("exam_id")
        if exam_id is not None and not user.has_role("admin"):
            exam = await db.get(Exam, exam_id)
            if exam is None:
                raise NotFoundError("Exam not found")
            if exam.owner_id != user.id:
                raise ForbiddenError("You do not own this exam")
        return await QuestService(db).create(user, rules, **data)


@router.get("/{quest_id}", response_model=QuestDetailOut)
async def get_quest(quest_id: uuid.UUID, user: CurrentUser, db: DbSession):
    service = QuestService(db)
    quest = await service.get_visible(quest_id, user)
    rules = await service.list_rules(quest_id)
    # Validate the base fields first: validating QuestDetailOut directly would
    # read the lazy ``rules`` relationship and raise MissingGreenlet.
    base = QuestOut.model_validate(quest)
    return QuestDetailOut(
        **base.model_dump(),
        rules=[QuestRuleOut.model_validate(r) for r in rules],
    )


@router.patch("/{quest_id}", response_model=QuestOut)
async def update_quest(quest_id: uuid.UUID, payload: QuestUpdate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await QuestService(db).update(
            quest_id, user, **payload.model_dump(exclude_unset=True)
        )


@router.delete("/{quest_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quest(quest_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        await QuestService(db).delete(quest_id, user)


@router.post("/{quest_id}/publish", response_model=QuestOut)
async def publish_quest(quest_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        return await QuestService(db).publish(quest_id, user)


@router.post("/{quest_id}/finalize", response_model=FinalizeResult)
async def finalize_quest(quest_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        service = QuestService(db)
        # Whether winners already existed decides if side effects (reward
        # notifications, badges) should fire — a re-finalize must be a no-op.
        already_finalized = (await service.get(quest_id)).status == "finalized"

        quest, winners = await service.finalize(quest_id, user)
        rules = {r.rank: r for r in await service.list_rules(quest_id)}

        from app.services.quest_finalize import apply_finalize_side_effects

        created = await apply_finalize_side_effects(
            db, quest, winners, already_finalized=already_finalized
        )
        out: list[WinnerOut] = [
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
    return FinalizeResult(quest_id=quest_id, winners=out, allocations_created=created)


@router.get("/{quest_id}/winners", response_model=list[WinnerOut])
async def list_winners(
    quest_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: LimitParam = 200,
    offset: OffsetParam = 0,
):
    service = QuestService(db)
    # A quest's winners are only readable where the quest itself is visible.
    await service.get_visible(quest_id, user)
    winners = await service.list_winners(quest_id, limit=limit, offset=offset)
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
