"""Task endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db.session import transaction
from app.models.quest import Task, TaskCompletion
from app.schemas.task import TaskCompletionOut, TaskCreate, TaskOut, TaskUpdate
from app.services.keys import task_reward_key
from app.services.reward_engine import RewardEngine
from app.services.social_service import NotificationService
from app.services.task_verification import verify_task_completion

router = APIRouter()


def _period_key(kind: str, now: datetime) -> str:
    """Bucket a completion by task kind so recurring tasks reset per period.

    Daily tasks bucket by calendar date, weekly by ISO year-week — both in
    ``settings.platform_timezone`` (default WIB) so a "day" resets at local
    midnight rather than 00:00 UTC. One-off tasks have an empty bucket
    (completed exactly once, forever).
    """
    local = now.astimezone(ZoneInfo(settings.platform_timezone))
    if kind == "daily":
        return local.strftime("%Y-%m-%d")
    if kind == "weekly":
        iso = local.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return ""


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    user: CurrentUser,
    db: DbSession,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
    q: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    """List tasks with role-aware visibility.

    Students (and the public) only ever see *available* tasks: active and
    currently inside their start/end window. Teachers and admins work from a
    management view and additionally see their own tasks regardless of active
    state or schedule — otherwise a draft, deactivated, or scheduled task
    would vanish from the very panel used to publish/edit it.

    ``scope=mine`` narrows a teacher/admin to tasks they own. ``status`` accepts
    ``active`` / ``inactive`` (by ``is_active``) or ``available`` (currently
    inside the window) and is only honoured for teacher/admin callers.
    """
    now = datetime.now(UTC)
    is_manager = user.has_role("teacher", "admin")

    stmt = select(Task).order_by(Task.created_at.desc())

    if is_manager:
        # Management view: every task the caller owns (admins see all).
        if scope == "mine" or not user.has_role("admin"):
            stmt = stmt.where(Task.owner_id == user.id)
        status_value = status.strip().lower() if status and status.strip() else None
        if status_value == "active":
            stmt = stmt.where(Task.is_active.is_(True))
        elif status_value == "inactive":
            stmt = stmt.where(Task.is_active.is_(False))
        elif status_value == "available":
            stmt = (
                stmt.where(Task.is_active.is_(True))
                .where((Task.starts_at.is_(None)) | (Task.starts_at <= now))
                .where((Task.ends_at.is_(None)) | (Task.ends_at >= now))
            )
        elif status_value == "scheduled":
            stmt = stmt.where(Task.is_active.is_(True)).where(Task.starts_at > now)
        elif status_value == "expired":
            stmt = stmt.where((Task.ends_at.is_not(None)) & (Task.ends_at < now))
    else:
        # Learner view: only tasks that are live right now.
        stmt = (
            stmt.where(Task.is_active.is_(True))
            .where((Task.starts_at.is_(None)) | (Task.starts_at <= now))
            .where((Task.ends_at.is_(None)) | (Task.ends_at >= now))
        )

    if q is not None and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(Task.title.ilike(term), Task.description.ilike(term)))
    if kind is not None and kind.strip():
        stmt = stmt.where(Task.kind == kind.strip())

    stmt = stmt.limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/me/completions", response_model=list[TaskCompletionOut])
async def list_my_completions(user: CurrentUser, db: DbSession):
    now = datetime.now(UTC)
    daily_period = _period_key("daily", now)
    weekly_period = _period_key("weekly", now)
    stmt = (
        select(TaskCompletion)
        .where(TaskCompletion.user_id == user.id)
        .where(TaskCompletion.period_key.in_(("", daily_period, weekly_period)))
        .order_by(TaskCompletion.completed_at.desc())
    )
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
        # Nullable columns may be explicitly cleared by sending ``null``; the
        # non-nullable ones (title/kind/reward_amount/is_active) only change when
        # a concrete value is provided, so a stray ``null`` cannot wipe them.
        nullable = {"description", "starts_at", "ends_at"}
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            if value is None and key not in nullable:
                continue
            setattr(task, key, value)
        starts, ends = task.starts_at, task.ends_at
        if starts is not None and ends is not None and ends <= starts:
            raise ConflictError("ends_at must be after starts_at")
        await db.flush()
    return TaskOut.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, user: TeacherUser, db: DbSession):
    async with transaction(db):
        task = await db.get(Task, task_id)
        if task is None:
            raise NotFoundError("Task not found")
        if not user.has_role("admin") and task.owner_id != user.id:
            raise ForbiddenError("You do not own this task")
        # Refuse once anyone has completed it, so reward history is not orphaned.
        completed = (
            await db.execute(
                select(TaskCompletion.id).where(TaskCompletion.task_id == task_id).limit(1)
            )
        ).scalar_one_or_none()
        if completed is not None:
            raise ConflictError("Cannot delete a task that has completions")
        await db.delete(task)
        await db.flush()


@router.post("/{task_id}/complete", response_model=TaskCompletionOut)
async def complete_task(task_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        task = await db.get(Task, task_id)
        if task is None or not task.is_active:
            raise NotFoundError("Task not found")
        now = datetime.now(UTC)
        # Enforce the full window (start *and* end), not just the end.
        if task.starts_at and now < task.starts_at:
            raise ConflictError("Task has not started yet")
        if task.ends_at and now > task.ends_at:
            raise ConflictError("Task has ended")

        # A task bound to a course/quest claims a specific real action
        # happened; verify it instead of trusting the self-report. Tasks with
        # neither binding remain genuinely honor-system.
        await verify_task_completion(db, task, user.id)

        period = _period_key(task.kind, now)
        existing = (
            await db.execute(
                select(TaskCompletion).where(
                    TaskCompletion.task_id == task_id,
                    TaskCompletion.user_id == user.id,
                    TaskCompletion.period_key == period,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("Task already completed for this period")

        rkey = task_reward_key(task_id, user.id, period)
        completion = TaskCompletion(
            task_id=task_id, user_id=user.id, period_key=period, reward_key=rkey
        )
        db.add(completion)
        await db.flush()
        if task.reward_amount > 0:
            await RewardEngine(db).allocate_task_reward(
                user=user, task_id=task_id, amount=task.reward_amount, rkey=rkey
            )
            await NotificationService(db).notify(
                user_id=user.id,
                kind="reward",
                title=f"Task complete: +{task.reward_amount} OPT",
                body=task.title,
                data={"task_id": str(task.id), "amount": task.reward_amount},
            )
    return TaskCompletionOut.model_validate(completion)
