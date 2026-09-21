"""Gamification endpoints: XP, level, and level-based leaderboard."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.errors import NotFoundError
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.services.gamification_service import GamificationService, level_for_xp

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/me")
async def my_gamification(user: CurrentUser, db: DbSession):
    """The caller's XP breakdown, level, and progress toward the next level."""
    return await GamificationService(db).xp_for_user(user.id)


@router.get("/levels")
async def levels(user: CurrentUser, db: DbSession, limit: int = 50):
    """Leaderboard ordered by XP (level), computed from real activity."""
    # Candidate set: active users with at least one graded attempt.
    graded = (
        select(ExamAttempt.user_id)
        .where(ExamAttempt.score_bp.is_not(None))
        .distinct()
        .scalar_subquery()
    )
    users = list(
        (
            await db.execute(
                select(User).where(User.is_active.is_(True), User.id.in_(graded)).limit(500)
            )
        )
        .scalars()
        .all()
    )
    xp_map = await GamificationService(db).xp_for_users([u.id for u in users])
    ranked = sorted(users, key=lambda u: (-xp_map.get(u.id, 0), str(u.id)))[:limit]
    entries = []
    for i, u in enumerate(ranked):
        xp = xp_map.get(u.id, 0)
        entries.append(
            {
                "user_id": str(u.id),
                "display_name": u.full_name,
                "rank": i + 1,
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
