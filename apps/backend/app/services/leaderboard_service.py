"""Materialized leaderboard snapshots.

The ranking endpoints aggregate from source tables in real time (cheap for the
current data size). For heavy scopes we can persist a snapshot into the
``leaderboards`` / ``leaderboard_entries`` tables, which also gives us a
stable, historical ranking that is independent of later score edits.

This is a deterministic rebuild: it fully replaces the entries for a scope.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.exam import ExamAttempt
from app.models.identity import User
from app.models.ranking import Leaderboard, LeaderboardEntry
from app.models.wallet import RewardAllocation

log = get_logger("leaderboard")


class LeaderboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def materialize_global(self, period: str = "all") -> int:
        """Rebuild the global leaderboard snapshot; returns entry count."""
        best_per_exam = (
            select(
                ExamAttempt.user_id.label("user_id"),
                func.max(ExamAttempt.score_bp).label("best"),
            )
            .where(ExamAttempt.score_bp.is_not(None))
            .where(ExamAttempt.is_flagged.is_(False))
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
        opc = (
            select(
                RewardAllocation.user_id.label("user_id"),
                func.coalesce(func.sum(RewardAllocation.amount), 0).label("opc"),
            )
            .where(RewardAllocation.status.in_(("pending", "confirmed")))
            .group_by(RewardAllocation.user_id)
            .subquery()
        )
        rows = (
            await self.session.execute(
                select(
                    User.id,
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
            )
        ).all()

        lb = (
            await self.session.execute(
                select(Leaderboard).where(
                    Leaderboard.scope == "global",
                    Leaderboard.scope_id.is_(None),
                    Leaderboard.period == period,
                )
            )
        ).scalar_one_or_none()
        if lb is None:
            lb = Leaderboard(scope="global", scope_id=None, period=period)
            self.session.add(lb)
            await self.session.flush()

        # Replace entries atomically.
        await self.session.execute(
            delete(LeaderboardEntry).where(LeaderboardEntry.leaderboard_id == lb.id)
        )
        for i, r in enumerate(rows, start=1):
            self.session.add(
                LeaderboardEntry(
                    leaderboard_id=lb.id,
                    user_id=r.id,
                    rank=i,
                    score_bp=int(r.score or 0),
                    opc_earned=int(r.opc or 0),
                )
            )
        lb.is_materialized = True
        await self.session.flush()
        log.info("leaderboard_materialized", scope="global", entries=len(rows))
        return len(rows)

    async def get_materialized(self, scope: str, period: str = "all") -> list[LeaderboardEntry]:
        lb = (
            await self.session.execute(
                select(Leaderboard).where(Leaderboard.scope == scope, Leaderboard.period == period)
            )
        ).scalar_one_or_none()
        if lb is None:
            return []
        return list(
            (
                await self.session.execute(
                    select(LeaderboardEntry)
                    .where(LeaderboardEntry.leaderboard_id == lb.id)
                    .order_by(LeaderboardEntry.rank)
                )
            )
            .scalars()
            .all()
        )
