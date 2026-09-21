"""Gamification: XP and leveling (deterministic simulation).

A player's XP is derived from activity that already exists in the system — it
is *computed*, never stored, so it can never drift out of sync:

  XP = sum(best exam score per exam, scaled)
     + quest-win XP (rank-weighted)
     + task-completion XP
     + badge points awarded

Level thresholds are a fixed, published table (quadratic-ish curve) so a level
is a pure function of XP. ``progress`` is the 0..1 fraction toward the next
level, which the UI renders as an XP bar.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import ExamAttempt
from app.models.quest import QuestWinner, TaskCompletion
from app.models.social import Badge, UserBadge

# XP contribution constants (documented so the simulation is transparent).
XP_PER_EXAM_POINT_BP = 1  # 1 XP per basis point of the best exam score
QUEST_RANK_XP = {1: 300, 2: 200, 3: 150}
XP_PER_TASK = 40
DEFAULT_QUEST_XP = 100  # for ranks beyond 3


def level_for_xp(xp: int) -> tuple[int, int, int]:
    """Return (level, current_level_xp, next_level_xp) for a total XP.

    Thresholds follow ``xp_for_level(n) = 500 * (n-1) * n // 2`` so each level
    costs progressively more. Level starts at 1 for 0 XP.
    """

    def xp_for_level(n: int) -> int:
        # cumulative XP required to *reach* level n
        return 500 * (n - 1) * n // 2

    level = 1
    while xp_for_level(level + 1) <= xp and level < 999:
        level += 1
    floor = xp_for_level(level)
    ceiling = xp_for_level(level + 1)
    return level, floor, ceiling


def level_progress(xp: int) -> float:
    level, floor, ceiling = level_for_xp(xp)
    span = max(1, ceiling - floor)
    return round((xp - floor) / span, 4)


class GamificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def xp_for_user(self, user_id: uuid.UUID) -> dict:
        """Compute a user's XP breakdown and level."""
        # Best exam score per exam (no retry double-counting).
        best_per_exam = (
            select(func.max(ExamAttempt.score_bp).label("best"))
            .where(ExamAttempt.user_id == user_id)
            .where(ExamAttempt.score_bp.is_not(None))
            .group_by(ExamAttempt.exam_id)
            .subquery()
        )
        exam_xp = (
            int(
                (
                    await self.session.execute(
                        select(func.coalesce(func.sum(best_per_exam.c.best), 0))
                    )
                ).scalar_one()
            )
            * XP_PER_EXAM_POINT_BP
        )

        # Quest wins.
        wins = (
            (
                await self.session.execute(
                    select(QuestWinner.rank).where(QuestWinner.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        quest_xp = sum(QUEST_RANK_XP.get(r, DEFAULT_QUEST_XP) for r in wins)

        # Task completions.
        tasks = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(TaskCompletion)
                    .where(TaskCompletion.user_id == user_id)
                )
            ).scalar_one()
        )
        task_xp = tasks * XP_PER_TASK

        # Badge points.
        badge_xp = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(Badge.points), 0))
                    .select_from(UserBadge)
                    .join(Badge, Badge.id == UserBadge.badge_id)
                    .where(UserBadge.user_id == user_id)
                )
            ).scalar_one()
        )

        total = exam_xp + quest_xp + task_xp + badge_xp
        level, floor, ceiling = level_for_xp(total)
        return {
            "xp": total,
            "level": level,
            "xp_into_level": total - floor,
            "xp_for_next_level": ceiling - floor,
            "progress": level_progress(total),
            "breakdown": {
                "exams": exam_xp,
                "quests": quest_xp,
                "tasks": task_xp,
                "badges": badge_xp,
            },
            "quest_wins": len(wins),
            "tasks_completed": tasks,
        }

    async def xp_for_users(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Bulk XP (exam + quest + task + badge) for many users at once."""
        if not user_ids:
            return {}
        totals: dict[uuid.UUID, int] = dict.fromkeys(user_ids, 0)

        best_per_exam = (
            select(
                ExamAttempt.user_id.label("user_id"),
                func.max(ExamAttempt.score_bp).label("best"),
            )
            .where(ExamAttempt.user_id.in_(user_ids))
            .where(ExamAttempt.score_bp.is_not(None))
            .group_by(ExamAttempt.user_id, ExamAttempt.exam_id)
            .subquery()
        )
        for uid, score in (
            await self.session.execute(
                select(best_per_exam.c.user_id, func.sum(best_per_exam.c.best)).group_by(
                    best_per_exam.c.user_id
                )
            )
        ).all():
            totals[uid] = totals.get(uid, 0) + int(score or 0) * XP_PER_EXAM_POINT_BP

        for uid, rank in (
            await self.session.execute(
                select(QuestWinner.user_id, QuestWinner.rank).where(
                    QuestWinner.user_id.in_(user_ids)
                )
            )
        ).all():
            totals[uid] = totals.get(uid, 0) + QUEST_RANK_XP.get(rank, DEFAULT_QUEST_XP)

        for uid, cnt in (
            await self.session.execute(
                select(TaskCompletion.user_id, func.count())
                .where(TaskCompletion.user_id.in_(user_ids))
                .group_by(TaskCompletion.user_id)
            )
        ).all():
            totals[uid] = totals.get(uid, 0) + int(cnt) * XP_PER_TASK

        for uid, pts in (
            await self.session.execute(
                select(UserBadge.user_id, func.coalesce(func.sum(Badge.points), 0))
                .join(Badge, Badge.id == UserBadge.badge_id)
                .where(UserBadge.user_id.in_(user_ids))
                .group_by(UserBadge.user_id)
            )
        ).all():
            totals[uid] = totals.get(uid, 0) + int(pts or 0)

        return totals
