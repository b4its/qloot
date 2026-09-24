"""Ranking endpoints: global, room, quest, and personal.

Computed on the fly with SQL aggregation (no N+1). A materialized
``leaderboards``/``leaderboard_entries`` snapshot can be built on demand
(admin) for heavy scopes — see ``LeaderboardService``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession, LimitParam, OffsetParam, OptionalUser
from app.core.config import settings
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.models.quest import QuestWinner
from app.models.wallet import RewardAllocation, WalletAccount

router = APIRouter()

PeriodParam = Literal["all", "weekly", "monthly"]


def _period_start(period: PeriodParam) -> datetime | None:
    """The inclusive start of a ranking period.

    "weekly" = the last 7 days, "monthly" = the last 30 days, anchored to the
    current instant in ``settings.platform_timezone`` so the window aligns
    with local time rather than UTC. ``None`` for "all" (no filter — lifetime
    ranking, the existing default behaviour).
    """
    if period == "all":
        return None
    tz = ZoneInfo(settings.platform_timezone)
    now_local = datetime.now(tz)
    days = 7 if period == "weekly" else 30
    return now_local - timedelta(days=days)


def _row(user_id, score_bp, opc, position, *, name: str | None = None) -> dict:
    return {
        "user_id": str(user_id),
        "rank": position,
        "score_bp": int(score_bp or 0),
        "opc_earned": int(opc or 0),
        "display_name": name,
    }


def _best_per_exam_subquery(*, room_exam_ids=None, period_start: datetime | None = None):
    """Best score per (user, exam) so retries never double-count.

    ``period_start`` scopes to attempts submitted on/after that instant (for
    weekly/monthly ranking windows); ``None`` means lifetime (no filter).
    """
    stmt = (
        select(
            ExamAttempt.user_id.label("user_id"),
            func.max(ExamAttempt.score_bp).label("best"),
        )
        .where(ExamAttempt.score_bp.is_not(None))
        .where(ExamAttempt.is_flagged.is_(False))
        .group_by(ExamAttempt.user_id, ExamAttempt.exam_id)
    )
    if room_exam_ids is not None:
        stmt = stmt.where(ExamAttempt.exam_id.in_(room_exam_ids))
    if period_start is not None:
        stmt = stmt.where(ExamAttempt.submitted_at >= period_start)
    return stmt.subquery()


@router.get("/global")
async def global_ranking(
    db: DbSession,
    user: CurrentUser,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
    period: PeriodParam = Query(default="all"),
):
    """Global leaderboard over each user's best-per-exam totals.

    Only active users who have at least one graded attempt are ranked, so the
    board is not padded with empty accounts. ``opc_earned`` reflects actual
    rewards (confirmed/pending), and ties break on user id for determinism.
    ``?period=weekly|monthly`` scopes exam totals to attempts submitted in the
    last 7/30 days; ``all`` (default) is lifetime.
    """
    best_per_exam = _best_per_exam_subquery(period_start=_period_start(period))
    totals = (
        select(
            best_per_exam.c.user_id.label("user_id"),
            func.coalesce(func.sum(best_per_exam.c.best), 0).label("score"),
        )
        .group_by(best_per_exam.c.user_id)
        .subquery()
    )
    opc = (
        select(
            RewardAllocation.user_id.label("user_id"),
            func.coalesce(func.sum(RewardAllocation.amount), 0).label("opc"),
        )
        .where(RewardAllocation.status.in_(("pending", "confirmed")))
        .group_by(RewardAllocation.user_id)
        .subquery()
    )
    stmt = (
        select(
            User.id,
            User.full_name,
            func.coalesce(totals.c.score, 0).label("score"),
            func.coalesce(opc.c.opc, 0).label("opc"),
        )
        .join(totals, totals.c.user_id == User.id)
        .outerjoin(opc, opc.c.user_id == User.id)
        .where(User.is_active.is_(True))
        .order_by(
            func.coalesce(totals.c.score, 0).desc(),
            func.coalesce(opc.c.opc, 0).desc(),
            User.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "scope": "global",
        "period": period,
        "entries": [
            _row(r.id, r.score, r.opc, i + 1, name=r.full_name) for i, r in enumerate(rows)
        ],
    }


@router.get("/rooms/{room_id}")
async def room_ranking(
    room_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: LimitParam = 50,
    offset: OffsetParam = 0,
):
    from app.models.exam import Exam
    from app.models.room import RoomMember
    from app.services.room_service import RoomService

    # A room's leaderboard inherits the room's read visibility: a private room's
    # roster/scores must not leak to non-members (404, like the room endpoints).
    await RoomService(db).get_visible(room_id, user)

    # Only count attempts for exams that belong to this room, otherwise scores
    # from unrelated exams would leak into the room leaderboard.
    room_exams = select(Exam.id).where(Exam.room_id == room_id).scalar_subquery()
    best_per_exam = _best_per_exam_subquery(room_exam_ids=room_exams)
    room_totals = (
        select(
            best_per_exam.c.user_id.label("user_id"),
            func.coalesce(func.sum(best_per_exam.c.best), 0).label("score"),
        )
        .group_by(best_per_exam.c.user_id)
        .subquery()
    )
    stmt = (
        select(
            RoomMember.user_id,
            User.full_name,
            func.coalesce(room_totals.c.score, 0).label("score"),
            func.coalesce(WalletAccount.cached_balance, 0).label("opc"),
        )
        .join(User, User.id == RoomMember.user_id)
        .outerjoin(room_totals, room_totals.c.user_id == RoomMember.user_id)
        .outerjoin(WalletAccount, WalletAccount.user_id == RoomMember.user_id)
        .where(RoomMember.room_id == room_id)
        .where(User.is_active.is_(True))
        .order_by(
            func.coalesce(room_totals.c.score, 0).desc(),
            func.coalesce(WalletAccount.cached_balance, 0).desc(),
            RoomMember.user_id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "scope": "room",
        "scope_id": str(room_id),
        "entries": [
            _row(r.user_id, r.score, r.opc, i + 1, name=r.full_name) for i, r in enumerate(rows)
        ],
    }


@router.get("/quests/{quest_id}")
async def quest_ranking(
    quest_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: LimitParam = 200,
    offset: OffsetParam = 0,
):
    from app.services.quest_service import QuestService

    # The quest leaderboard inherits the quest's read visibility (draft quests
    # are not enumerable by id).
    await QuestService(db).get_visible(quest_id, user)
    stmt = (
        select(QuestWinner, User.full_name, RewardAllocation.amount, RewardAllocation.status)
        .join(User, User.id == QuestWinner.user_id)
        .outerjoin(RewardAllocation, RewardAllocation.reward_key == QuestWinner.reward_key)
        .where(QuestWinner.quest_id == quest_id)
        .order_by(QuestWinner.rank)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "scope": "quest",
        "scope_id": str(quest_id),
        "entries": [
            {
                "user_id": str(w.user_id),
                "rank": w.rank,
                "score_bp": int(w.score_bp or 0),
                # The real reward for this winner (0 until the allocation exists,
                # i.e. before finalize, or if it was cancelled).
                "opc_earned": (int(amount or 0) if status in ("pending", "confirmed") else 0),
                "display_name": name,
                "duration_seconds": w.duration_seconds,
                "submitted_at": w.submitted_at.isoformat() if w.submitted_at else None,
            }
            for w, name, amount, status in rows
        ],
    }


@router.get("/me")
async def my_ranking(db: DbSession, user: CurrentUser, period: PeriodParam = Query(default="all")):
    """The caller's own total, OPT balance, and live global position.

    ``?period=weekly|monthly`` must agree with ``/rankings/global`` for the
    same value so the personal card's rank matches the row the user sees
    there.
    """
    # Use the *same* best-per-exam aggregation as the global board so the
    # caller's own total and rank agree with their global position. Retries must
    # not double-count and flagged attempts must be excluded — re-implementing
    # the sum here previously diverged from ``global_ranking``.
    best_per_exam = _best_per_exam_subquery(period_start=_period_start(period))
    totals = (
        select(
            best_per_exam.c.user_id.label("user_id"),
            func.coalesce(func.sum(best_per_exam.c.best), 0).label("score"),
        )
        .group_by(best_per_exam.c.user_id)
        .subquery()
    )
    total = (
        await db.execute(
            select(func.coalesce(totals.c.score, 0)).where(totals.c.user_id == user.id)
        )
    ).scalar_one_or_none()
    account = (
        await db.execute(select(WalletAccount).where(WalletAccount.user_id == user.id))
    ).scalar_one_or_none()

    # Position must use the *same* 3-key ordering as ``global_ranking``
    # (score desc, opc desc, id asc) so the personal card's rank matches the
    # row the user sees in the global table (they previously diverged on ties).
    mine_score = int(total or 0)
    mine_opc = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(RewardAllocation.amount), 0)).where(
                    RewardAllocation.user_id == user.id,
                    RewardAllocation.status.in_(("pending", "confirmed")),
                )
            )
        ).scalar_one()
    )
    # ``opc`` subquery mirrors global_ranking: lifetime earned (pending+confirmed).
    opc = (
        select(
            RewardAllocation.user_id.label("user_id"),
            func.coalesce(func.sum(RewardAllocation.amount), 0).label("opc"),
        )
        .where(RewardAllocation.status.in_(("pending", "confirmed")))
        .group_by(RewardAllocation.user_id)
        .subquery()
    )
    ranked = (
        select(
            User.id.label("user_id"),
            func.coalesce(totals.c.score, 0).label("score"),
            func.coalesce(opc.c.opc, 0).label("opc"),
        )
        .join(totals, totals.c.user_id == User.id)
        .outerjoin(opc, opc.c.user_id == User.id)
        .where(User.is_active.is_(True))
        .subquery()
    )
    # Count active users who sort strictly before the caller.
    before = (
        (ranked.c.score > mine_score)
        | ((ranked.c.score == mine_score) & (ranked.c.opc > mine_opc))
        | (
            (ranked.c.score == mine_score)
            & (ranked.c.opc == mine_opc)
            & (ranked.c.user_id < user.id)
        )
    )
    higher = (await db.execute(select(func.count()).select_from(ranked).where(before))).scalar_one()
    # Level/XP enrich the personal card.
    from app.services.gamification_service import GamificationService

    xp = await GamificationService(db).xp_for_user(user.id)
    return {
        "user_id": str(user.id),
        "period": period,
        "total_score_bp": int(total or 0),
        "opc_balance": int(account.cached_balance if account else 0),
        "rank": int(higher) + 1,
        "xp": xp["xp"],
        "level": xp["level"],
        "level_progress": xp["progress"],
    }


@router.get("/leaderboards")
async def list_materialized(
    db: DbSession, user: OptionalUser, limit: LimitParam = 20, offset: OffsetParam = 0
):
    """List materialized leaderboard snapshots (if any have been built)."""
    from app.models.ranking import Leaderboard

    stmt = select(Leaderboard).order_by(Leaderboard.updated_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(lb.id),
            "scope": lb.scope,
            "scope_id": str(lb.scope_id) if lb.scope_id else None,
            "period": lb.period,
            "is_materialized": lb.is_materialized,
            "updated_at": lb.updated_at.isoformat(),
        }
        for lb in rows
    ]


@router.post("/leaderboards/refresh")
async def refresh_materialized(db: DbSession, admin: AdminUser):
    """Rebuild the materialized global leaderboard snapshot (admin only)."""
    from app.services.leaderboard_service import LeaderboardService

    count = await LeaderboardService(db).materialize_global()
    return {"materialized": count}
