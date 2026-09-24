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
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.exam import ExamAttempt
from app.models.learning import LessonProgress
from app.models.quest import QuestAttempt, QuestWinner, TaskCompletion
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

    async def activity_dates_for_user(self, user_id: uuid.UUID) -> set[date]:
        """Distinct calendar dates (in ``settings.platform_timezone``) on
        which the user did something that counts toward a streak: completed a
        lesson, submitted an exam attempt, submitted a quest attempt, or
        completed a task. Derived from real rows every call — never stored,
        so it can never drift (same principle as XP).
        """
        tz = ZoneInfo(settings.platform_timezone)
        timestamps: list = []

        timestamps += (
            (
                await self.session.execute(
                    select(LessonProgress.completed_at).where(
                        LessonProgress.user_id == user_id,
                        LessonProgress.completed.is_(True),
                        LessonProgress.completed_at.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        timestamps += (
            (
                await self.session.execute(
                    select(ExamAttempt.submitted_at).where(
                        ExamAttempt.user_id == user_id,
                        ExamAttempt.submitted_at.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        timestamps += (
            (
                await self.session.execute(
                    select(QuestAttempt.submitted_at).where(QuestAttempt.user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        timestamps += (
            (
                await self.session.execute(
                    select(TaskCompletion.completed_at).where(
                        TaskCompletion.user_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        return {ts.astimezone(tz).date() for ts in timestamps if ts is not None}

    async def streak_for_user(self, user_id: uuid.UUID) -> dict:
        """Current and best consecutive-day activity streak.

        "Current" counts backward from today (platform tz); a gap since
        yesterday breaks it (today not yet active still counts an
        in-progress streak ending yesterday, so completing something later
        today does not reset it to zero at midnight).
        """
        dates = await self.activity_dates_for_user(user_id)
        if not dates:
            return {"current_streak": 0, "best_streak": 0, "last_active_date": None}

        tz = ZoneInfo(settings.platform_timezone)
        today = datetime.now(tz).date()

        ordered = sorted(dates, reverse=True)
        last_active = ordered[0]

        # Current streak: walk backward from the most recent active day only
        # if it is today or yesterday (otherwise the streak is already over).
        current = 0
        if last_active in (today, today - timedelta(days=1)):
            cursor = last_active
            while cursor in dates:
                current += 1
                cursor -= timedelta(days=1)

        # Best streak ever: scan all dates for the longest consecutive run.
        best = 0
        run = 0
        prev: date | None = None
        for d in sorted(dates):
            if prev is not None and d == prev + timedelta(days=1):
                run += 1
            else:
                run = 1
            best = max(best, run)
            prev = d

        return {
            "current_streak": current,
            "best_streak": best,
            "last_active_date": last_active.isoformat(),
        }

    async def notify_level_up_if_crossed(self, *, user_id: uuid.UUID, level: int) -> bool:
        """Emit exactly one level-up notification (and optional OPT bonus)
        the first time the caller's derived level is observed to have
        crossed a new threshold. Idempotent: repeated calls at the same
        level are a no-op because ``last_notified_level`` is only ever
        advanced, never re-read as "not yet notified" for a level already
        recorded.
        """
        from app.core.config import settings
        from app.models.social import UserProgress

        row = await self.session.get(UserProgress, user_id)
        if row is None:
            row = UserProgress(user_id=user_id, last_notified_level=1)
            self.session.add(row)
            await self.session.flush()

        if level <= row.last_notified_level:
            return False

        previous_level = row.last_notified_level
        row.last_notified_level = level
        await self.session.flush()

        from app.services.keys import level_up_reward_key
        from app.services.reward_engine import RewardEngine
        from app.services.social_service import NotificationService

        bonus = settings.reward_level_up
        if bonus > 0:
            from app.models.identity import User

            user = await self.session.get(User, user_id)
            if user is not None:
                rkey = level_up_reward_key(user_id, level)
                await RewardEngine(self.session).credit(
                    user=user,
                    amount=bonus,
                    reference_type="level_up",
                    reference_id=f"level-{level}",
                    reward_key_value=rkey,
                    token_id=0,
                )

        await NotificationService(self.session).notify(
            user_id=user_id,
            kind="level",
            title=f"Naik ke level {level}!",
            body=(
                f"Kamu naik dari level {previous_level} ke level {level}"
                + (f" (+{bonus} OPT)" if bonus > 0 else "")
                + "."
            ),
            data={"level": level, "previous_level": previous_level, "bonus_opt": bonus},
        )
        return True

    async def xp_for_user(self, user_id: uuid.UUID) -> dict:
        """Compute a user's XP breakdown and level."""
        # Best exam score per exam (no retry double-counting). Flagged
        # (disqualified) attempts are excluded so XP/level agree with the score
        # leaderboards (which also drop flagged attempts).
        best_per_exam = (
            select(func.max(ExamAttempt.score_bp).label("best"))
            .where(ExamAttempt.user_id == user_id)
            .where(ExamAttempt.score_bp.is_not(None))
            .where(ExamAttempt.is_flagged.is_(False))
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
            .where(ExamAttempt.is_flagged.is_(False))
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
