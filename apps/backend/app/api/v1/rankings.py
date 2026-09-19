"""Ranking endpoints: global, room, quest, and personal.

Computed on the fly with SQL aggregation (no N+1). A materialized leaderboard
table exists for future heavy use; here we aggregate from source tables.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.models.quest import QuestWinner
from app.models.wallet import WalletAccount

router = APIRouter()


def _row(user_id, score_bp, opc, position) -> dict:
    return {
        "user_id": str(user_id),
        "rank": position,
        "score_bp": int(score_bp or 0),
        "opc_earned": int(opc or 0),
    }


@router.get("/global")
async def global_ranking(db: DbSession, user: CurrentUser, limit: int = 50):
    # Best score per (user, exam) so retries don't double-count, then sum across
    # exams for the global total.
    best_per_exam = (
        select(
            ExamAttempt.user_id.label("user_id"),
            func.max(ExamAttempt.score_bp).label("best"),
        )
        .where(ExamAttempt.score_bp.is_not(None))
        .group_by(ExamAttempt.user_id, ExamAttempt.exam_id)
        .subquery()
    )
    totals = (
        select(
            best_per_exam.c.user_id.label("user_id"),
            func.coalesce(func.sum(best_per_exam.c.best), 0).label("score"),
        )
        .group_by(best_per_exam.c.user_id)
        .subquery()
    )
    stmt = (
        select(
            User.id,
            func.coalesce(totals.c.score, 0).label("score"),
            func.coalesce(WalletAccount.cached_balance, 0).label("opc"),
        )
        .outerjoin(totals, totals.c.user_id == User.id)
        .outerjoin(WalletAccount, WalletAccount.user_id == User.id)
        .group_by(User.id, totals.c.score, WalletAccount.cached_balance)
        .order_by(func.coalesce(totals.c.score, 0).desc(), User.id.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "scope": "global",
        "entries": [_row(r.id, r.score, r.opc, i + 1) for i, r in enumerate(rows)],
    }


@router.get("/rooms/{room_id}")
async def room_ranking(room_id: uuid.UUID, db: DbSession, user: CurrentUser, limit: int = 50):
    from app.models.exam import Exam
    from app.models.room import RoomMember

    # Only count attempts for exams that belong to this room, otherwise scores
    # from unrelated exams would leak into the room leaderboard. Use the best
    # score per (user, exam) so retries don't double-count.
    room_exams = select(Exam.id).where(Exam.room_id == room_id).scalar_subquery()
    best_per_exam = (
        select(
            ExamAttempt.user_id.label("user_id"),
            func.max(ExamAttempt.score_bp).label("best"),
        )
        .where(ExamAttempt.score_bp.is_not(None))
        .where(ExamAttempt.exam_id.in_(room_exams))
        .group_by(ExamAttempt.user_id, ExamAttempt.exam_id)
        .subquery()
    )
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
            func.coalesce(room_totals.c.score, 0).label("score"),
        )
        .outerjoin(room_totals, room_totals.c.user_id == RoomMember.user_id)
        .where(RoomMember.room_id == room_id)
        .order_by(func.coalesce(room_totals.c.score, 0).desc(), RoomMember.user_id.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "scope": "room",
        "scope_id": str(room_id),
        "entries": [_row(r.user_id, r.score, 0, i + 1) for i, r in enumerate(rows)],
    }


@router.get("/quests/{quest_id}")
async def quest_ranking(quest_id: uuid.UUID, db: DbSession, user: CurrentUser):
    stmt = select(QuestWinner).where(QuestWinner.quest_id == quest_id).order_by(QuestWinner.rank)
    winners = (await db.execute(stmt)).scalars().all()
    return {
        "scope": "quest",
        "scope_id": str(quest_id),
        "entries": [_row(w.user_id, w.score_bp, 0, w.rank) for w in winners],
    }


@router.get("/me")
async def my_ranking(db: DbSession, user: CurrentUser):
    # Best score per exam, summed — consistent with the global leaderboard.
    best_per_exam = (
        select(func.max(ExamAttempt.score_bp).label("best"))
        .where(ExamAttempt.user_id == user.id)
        .where(ExamAttempt.score_bp.is_not(None))
        .group_by(ExamAttempt.exam_id)
        .subquery()
    )
    total = (
        await db.execute(select(func.coalesce(func.sum(best_per_exam.c.best), 0)))
    ).scalar_one()
    account = (
        await db.execute(select(WalletAccount).where(WalletAccount.user_id == user.id))
    ).scalar_one_or_none()
    return {
        "user_id": str(user.id),
        "total_score_bp": int(total or 0),
        "opc_balance": int(account.cached_balance if account else 0),
    }
