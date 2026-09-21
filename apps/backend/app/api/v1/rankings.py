"""Ranking endpoints: global, room, quest, and personal.

Computed on the fly with SQL aggregation (no N+1). A materialized
``leaderboards``/``leaderboard_entries`` snapshot can be built on demand
(admin) for heavy scopes — see ``LeaderboardService``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession, LimitParam, OptionalUser
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.models.quest import QuestWinner
from app.models.wallet import RewardAllocation, WalletAccount

router = APIRouter()


def _row(user_id, score_bp, opc, position, *, name: str | None = None) -> dict:
    return {
        "user_id": str(user_id),
        "rank": position,
        "score_bp": int(score_bp or 0),
        "opc_earned": int(opc or 0),
        "display_name": name,
    }


def _best_per_exam_subquery(*, room_exam_ids=None):
    """Best score per (user, exam) so retries never double-count."""
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
    return stmt.subquery()


@router.get("/global")
async def global_ranking(db: DbSession, user: CurrentUser, limit: LimitParam = 50):
    """Global leaderboard over each user's best-per-exam totals.

    Only active users who have at least one graded attempt are ranked, so the
    board is not padded with empty accounts. ``opc_earned`` reflects actual
    rewards (confirmed/pending), and ties break on user id for determinism.
    """
    best_per_exam = _best_per_exam_subquery()
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
    )
    rows = (await db.execute(stmt)).all()
    return {
        "scope": "global",
        "entries": [
            _row(r.id, r.score, r.opc, i + 1, name=r.full_name) for i, r in enumerate(rows)
        ],
    }


@router.get("/rooms/{room_id}")
async def room_ranking(
    room_id: uuid.UUID, db: DbSession, user: CurrentUser, limit: LimitParam = 50
):
    from app.models.exam import Exam
    from app.models.room import RoomMember

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
async def quest_ranking(quest_id: uuid.UUID, db: DbSession, user: CurrentUser):
    stmt = (
        select(QuestWinner, User.full_name)
        .join(User, User.id == QuestWinner.user_id)
        .where(QuestWinner.quest_id == quest_id)
        .order_by(QuestWinner.rank)
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
                "opc_earned": 0,
                "display_name": name,
                "duration_seconds": w.duration_seconds,
                "submitted_at": w.submitted_at.isoformat() if w.submitted_at else None,
            }
            for w, name in rows
        ],
    }


@router.get("/me")
async def my_ranking(db: DbSession, user: CurrentUser):
    """The caller's own total, OPC balance, and live global position."""
    # Use the *same* best-per-exam aggregation as the global board so the
    # caller's own total and rank agree with their global position. Retries must
    # not double-count and flagged attempts must be excluded — re-implementing
    # the sum here previously diverged from ``global_ranking``.
    best_per_exam = _best_per_exam_subquery()
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

    # Position: count active users with a strictly higher total.
    higher = (
        await db.execute(
            select(func.count())
            .select_from(totals)
            .join(User, User.id == totals.c.user_id)
            .where(User.is_active.is_(True), totals.c.score > int(total or 0))
        )
    ).scalar_one()
    # Level/XP enrich the personal card.
    from app.services.gamification_service import GamificationService

    xp = await GamificationService(db).xp_for_user(user.id)
    return {
        "user_id": str(user.id),
        "total_score_bp": int(total or 0),
        "opc_balance": int(account.cached_balance if account else 0),
        "rank": int(higher) + 1,
        "xp": xp["xp"],
        "level": xp["level"],
        "level_progress": xp["progress"],
    }


@router.get("/leaderboards")
async def list_materialized(db: DbSession, user: OptionalUser, limit: LimitParam = 20):
    """List materialized leaderboard snapshots (if any have been built)."""
    from app.models.ranking import Leaderboard

    stmt = select(Leaderboard).order_by(Leaderboard.updated_at.desc()).limit(limit)
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
