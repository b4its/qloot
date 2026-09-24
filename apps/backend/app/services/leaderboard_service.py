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

    async def get_materialized(
        self, scope: str, period: str = "all", *, scope_id=None
    ) -> list[LeaderboardEntry]:
        stmt = select(Leaderboard).where(Leaderboard.scope == scope, Leaderboard.period == period)
        stmt = (
            stmt.where(Leaderboard.scope_id == scope_id)
            if scope_id is not None
            else stmt.where(Leaderboard.scope_id.is_(None))
        )
        lb = (await self.session.execute(stmt)).scalar_one_or_none()
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

    async def materialize_room(self, room_id, period: str = "all") -> int:
        """Rebuild a room's leaderboard snapshot; returns entry count.

        Same scoring as the live ``GET /rankings/rooms/{id}`` endpoint (best
        score per exam belonging to the room), but persisted so a closed
        room's final standings survive later score edits elsewhere.
        """
        import uuid as _uuid

        from app.models.exam import Exam
        from app.models.room import RoomMember

        room_exams = select(Exam.id).where(Exam.room_id == room_id).scalar_subquery()
        best_per_exam = (
            select(
                ExamAttempt.user_id.label("user_id"),
                func.max(ExamAttempt.score_bp).label("best"),
            )
            .where(ExamAttempt.score_bp.is_not(None))
            .where(ExamAttempt.is_flagged.is_(False))
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
        rows = (
            await self.session.execute(
                select(
                    RoomMember.user_id,
                    func.coalesce(room_totals.c.score, 0).label("score"),
                )
                .join(User, User.id == RoomMember.user_id)
                .outerjoin(room_totals, room_totals.c.user_id == RoomMember.user_id)
                .where(RoomMember.room_id == room_id)
                .where(User.is_active.is_(True))
                .order_by(func.coalesce(room_totals.c.score, 0).desc(), RoomMember.user_id.asc())
            )
        ).all()
        return await self._replace_entries(
            "room",
            room_id if isinstance(room_id, _uuid.UUID) else _uuid.UUID(str(room_id)),
            rows,
            period,
        )

    async def materialize_quest(self, quest_id, period: str = "all") -> int:
        """Rebuild a quest's winner snapshot; returns entry count."""
        import uuid as _uuid

        from app.models.quest import QuestWinner

        rows = (
            await self.session.execute(
                select(QuestWinner.user_id, QuestWinner.score_bp)
                .where(QuestWinner.quest_id == quest_id)
                .order_by(QuestWinner.rank)
            )
        ).all()
        return await self._replace_entries(
            "quest",
            quest_id if isinstance(quest_id, _uuid.UUID) else _uuid.UUID(str(quest_id)),
            rows,
            period,
        )

    async def _replace_entries(self, scope: str, scope_id, rows, period: str) -> int:
        lb = (
            await self.session.execute(
                select(Leaderboard).where(
                    Leaderboard.scope == scope,
                    Leaderboard.scope_id == scope_id,
                    Leaderboard.period == period,
                )
            )
        ).scalar_one_or_none()
        if lb is None:
            lb = Leaderboard(scope=scope, scope_id=scope_id, period=period)
            self.session.add(lb)
            await self.session.flush()

        await self.session.execute(
            delete(LeaderboardEntry).where(LeaderboardEntry.leaderboard_id == lb.id)
        )
        for i, r in enumerate(rows, start=1):
            self.session.add(
                LeaderboardEntry(
                    leaderboard_id=lb.id,
                    user_id=r[0],
                    rank=i,
                    score_bp=int(r[1] or 0),
                    opc_earned=0,
                )
            )
        lb.is_materialized = True
        await self.session.flush()
        log.info("leaderboard_materialized", scope=scope, scope_id=str(scope_id), entries=len(rows))
        return len(rows)
