"""Gamification endpoints: XP, level, and level-based leaderboard."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam
from app.core.errors import NotFoundError
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.services.gamification_service import GamificationService, level_for_xp

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/me")
async def my_gamification(user: CurrentUser, db: DbSession):
    """The caller's XP breakdown, level, and progress toward the next level."""
    service = GamificationService(db)
    result = await service.xp_for_user(user.id)
    # Award any XP-milestone badges the user has crossed (keeps the badge page
    # free of permanently-locked filler; idempotent).
    from app.db.session import transaction
    from app.services.social_service import BadgeService

    async with transaction(db):
        await BadgeService(db).sync_xp_milestones(user=user, xp=int(result["xp"]))
    return result


@router.get("/levels")
async def levels(user: CurrentUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0):
    """Leaderboard ordered by XP (level), computed from real activity.

    Every active user with at least one graded attempt is ranked by their *full*
    XP (exam + quest + task + badge) so the order and the displayed value agree,
    and the window is an exact slice (the previous 500-row cap truncated the
    board before sorting).
    """
    graded = (
        select(ExamAttempt.user_id)
        .where(ExamAttempt.score_bp.is_not(None))
        .where(ExamAttempt.is_flagged.is_(False))
        .distinct()
        .scalar_subquery()
    )
    users = list(
        (await db.execute(select(User).where(User.is_active.is_(True), User.id.in_(graded))))
        .scalars()
        .all()
    )
    xp_map = await GamificationService(db).xp_for_users([u.id for u in users])
    ordered = sorted(users, key=lambda u: (-xp_map.get(u.id, 0), str(u.id)))
    window = ordered[offset : offset + limit]
    entries = []
    for i, u in enumerate(window):
        xp = xp_map.get(u.id, 0)
        entries.append(
            {
                "user_id": str(u.id),
                "display_name": u.full_name,
                "rank": offset + i + 1,
                "xp": xp,
                "level": level_for_xp(xp)[0],
            }
        )
    return {"scope": "levels", "entries": entries}


@router.get("/levels/{user_id}")
async def user_level(user_id: str, user: CurrentUser, db: DbSession):
    """Public level card for a user (used by profile tooltips)."""
    import uuid as _uuid

    try:
        target_id = _uuid.UUID(user_id)
    except ValueError as exc:
        raise NotFoundError("User not found") from exc
    target = await db.get(User, target_id)
    if target is None:
        raise NotFoundError("User not found")
    return await GamificationService(db).xp_for_user(target.id)
