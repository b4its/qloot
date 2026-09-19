"""Task endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.session import transaction
from app.models.quest import Task, TaskCompletion
from app.schemas.task import TaskCompletionOut, TaskCreate, TaskOut, TaskUpdate
from app.services.keys import task_reward_key
from app.services.reward_engine import RewardEngine
from app.services.social_service import NotificationService

router = APIRouter()


@router.get("", response_model=list[TaskOut])
async def list_tasks(user: CurrentUser, db: DbSession, limit: int = 50, offset: int = 0):
    stmt = select(Task).where(Task.is_active.is_(True)).order_by(Task.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        task = Task(owner_id=user.id, **payload.model_dump())
        db.add(task)
        await db.flush()
    return TaskOut.model_validate(task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: uuid.UUID, payload: TaskUpdate, user: TeacherUser, db: DbSession):
    async with transaction(db):
        task = await db.get(Task, task_id)
        if task is None:
            raise NotFoundError("Task not found")
        if not user.has_role("admin") and task.owner_id != user.id:
            raise ForbiddenError("You do not own this task")
        for k, v in payload.model_dump(exclude_unset=True).items():
            if v is not None:
                setattr(task, k, v)
        await db.flush()
    return TaskOut.model_validate(task)


@router.post("/{task_id}/complete", response_model=TaskCompletionOut)
async def complete_task(task_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        task = await db.get(Task, task_id)
        if task is None or not task.is_active:
            raise NotFoundError("Task not found")
        now = datetime.now(UTC)
        if task.ends_at and now > task.ends_at:
            raise ConflictError("Task has ended")

        existing = (
            await db.execute(
                select(TaskCompletion).where(
                    TaskCompletion.task_id == task_id, TaskCompletion.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Task already completed")

        rkey = task_reward_key(task_id, user.id)
        completion = TaskCompletion(task_id=task_id, user_id=user.id, reward_key=rkey)
        db.add(completion)
        await db.flush()
        if task.reward_amount > 0:
            await RewardEngine(db).allocate_task_reward(
                user=user, task_id=task_id, amount=task.reward_amount, rkey=rkey
            )
            await NotificationService(db).notify(
                user_id=user.id,
                kind="reward",
                title=f"Task complete: +{task.reward_amount} OPC",
                body=task.title,
                data={"task_id": str(task.id), "amount": task.reward_amount},
            )
    return TaskCompletionOut.model_validate(completion)
