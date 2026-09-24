"""Notification & badge services."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.identity import User
from app.models.social import Badge, Notification, UserBadge

log = get_logger("social")

# Earnable XP-milestone badges: (xp_threshold, code, name, description, icon, points).
# Every entry is reachable — BadgeService.sync_xp_milestones awards the ones a
# user has crossed. Keeping the catalog == the awardable set means the badge
# page never shows permanently-locked filler.
XP_MILESTONES: list[tuple[int, str, str, str, str, int]] = [
    (500, "xp_500", "Rising Star", "Raih 500 XP", "⭐", 10),
    (2_000, "xp_2000", "Achiever", "Raih 2.000 XP", "🌟", 20),
    (5_000, "xp_5000", "High Achiever", "Raih 5.000 XP", "💠", 30),
    (10_000, "xp_10000", "Scholar", "Raih 10.000 XP", "🎓", 50),
    (25_000, "xp_25000", "Master Scholar", "Raih 25.000 XP", "🏆", 80),
]


def _milestone_badge_row(code: str, name: str, desc: str, icon: str, points: int) -> dict:
    return {
        "code": code,
        "name": name,
        "description": desc,
        "icon": icon,
        "points": points,
        "rarity": rarity_for_points(points),
    }


def rarity_for_points(points: int) -> str:
    """Deterministic points -> rarity tier mapping (matches the migration's
    backfill so newly-seeded and pre-existing badges agree).
    """
    if points >= 100:
        return "legendary"
    if points >= 40:
        return "epic"
    if points >= 20:
        return "rare"
    return "common"


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def notify(
        self,
        *,
        user_id: uuid.UUID,
        kind: str,
        title: str,
        body: str | None = None,
        data: dict | None = None,
    ) -> Notification:
        n = Notification(user_id=user_id, kind=kind, title=title, body=body, data=data)
        self.session.add(n)
        await self.session.flush()
        return n

    async def notify_many(
        self,
        *,
        user_ids: list[uuid.UUID],
        kind: str,
        title: str,
        body: str | None = None,
        data: dict | None = None,
    ) -> int:
        count = 0
        for uid in user_ids:
            self.session.add(
                Notification(user_id=uid, kind=kind, title=title, body=body, data=data)
            )
            count += 1
        await self.session.flush()
        return count

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0, unread_only: bool = False
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        return list((await self.session.execute(stmt)).scalars().all())

    async def unread_count(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
        n = await self.session.get(Notification, notification_id)
        if n is None or n.user_id != user_id:
            raise NotFoundError("Notification not found")
        if n.read_at is None:
            from datetime import UTC, datetime

            n.read_at = datetime.now(UTC)
            await self.session.flush()
        return n

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        from datetime import UTC, datetime

        rows = await self.session.execute(
            select(Notification).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
        items = rows.scalars().all()
        for n in items:
            n.read_at = datetime.now(UTC)
        await self.session.flush()
        return len(items)


class BadgeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_catalog(self) -> None:
        """Idempotently seed the badge catalog.

        Uses INSERT ... ON CONFLICT DO NOTHING so concurrent startups cannot
        race the `code` unique constraint.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        catalog = [
            ("first_quest", "First Quest", "Completed your first quest", "🎯", 10),
            ("quiz_master", "Quiz Master", "Aced a multiple-choice quiz", "🧠", 25),
            ("top_3", "Podium Finish", "Finished in the top 3 of a quest", "🥉", 50),
            ("first_reward", "First OPT", "Earned your first OryphemToken", "💎", 15),
            ("room_regular", "Room Regular", "Joined 5 rooms", "🎪", 20),
            ("perfect_exam", "Perfect Score", "Scored 100% on an exam", "🌟", 40),
            ("learner", "Dedicated Learner", "Completed 5 lessons", "📚", 30),
            # XP-milestone badges (awarded by sync_xp_milestones) — included so
            # every catalogued badge is reachable.
            *[
                (code, name, desc, icon, points)
                for _, code, name, desc, icon, points in XP_MILESTONES
            ],
        ]
        rows = [
            {
                "code": code,
                "name": name,
                "description": desc,
                "icon": icon,
                "points": points,
                "rarity": rarity_for_points(points),
            }
            for code, name, desc, icon, points in catalog
        ]
        await self.session.execute(
            pg_insert(Badge).values(rows).on_conflict_do_nothing(index_elements=["code"])
        )
        await self.session.flush()

    async def award(
        self, *, user: User, code: str, meta: dict | None = None, notify: bool = True
    ) -> UserBadge | None:
        """Award a badge idempotently. Returns None if already owned."""
        badge = (
            await self.session.execute(select(Badge).where(Badge.code == code))
        ).scalar_one_or_none()
        if badge is None:
            # The catalog may not have been seeded yet (e.g. the very first
            # award). Ensure it exists so the award can proceed.
            await self.ensure_catalog()
            badge = (
                await self.session.execute(select(Badge).where(Badge.code == code))
            ).scalar_one_or_none()
        if badge is None:
            return None
        existing = (
            await self.session.execute(
                select(UserBadge).where(
                    UserBadge.user_id == user.id, UserBadge.badge_id == badge.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return None
        ub = UserBadge(user_id=user.id, badge_id=badge.id, meta=meta)
        try:
            # SAVEPOINT so a concurrent award of the same badge (unique on
            # user_id+badge_id) is a harmless no-op instead of a 500.
            async with self.session.begin_nested():
                self.session.add(ub)
                await self.session.flush()
        except IntegrityError:
            return None
        # Badges are an off-chain gamification concept in QLoot; the on-chain
        # contracts hold the fungible assets (OPT/QTC/ORT) only, so nothing is
        # mirrored on-chain for a badge award.
        if notify:
            await NotificationService(self.session).notify(
                user_id=user.id,
                kind="badge",
                title=f"Badge unlocked: {badge.name}",
                body=badge.description,
                data={"code": badge.code, "icon": badge.icon, "points": badge.points},
            )
        log.info("badge_awarded", user_id=str(user.id), code=code)
        return ub

    async def sync_xp_milestones(self, *, user: User, xp: int) -> int:
        """Award every XP-milestone badge the user has crossed (idempotent).

        Returns the number of newly-awarded badges. Called from the gamification
        endpoint so levels/badges stay in step without a background job.
        """
        await self.ensure_catalog()
        awarded = 0
        for threshold, code, _name, _desc, _icon, _points in XP_MILESTONES:
            if xp < threshold:
                continue
            if await self.award(user=user, code=code, meta={"xp": xp}) is not None:
                awarded += 1
        return awarded

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 200, offset: int = 0
    ) -> list[tuple[UserBadge, Badge]]:
        stmt = (
            select(UserBadge, Badge)
            .join(Badge, Badge.id == UserBadge.badge_id)
            .where(UserBadge.user_id == user_id)
            .order_by(UserBadge.awarded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    async def catalog(self) -> list[Badge]:
        return list(
            (await self.session.execute(select(Badge).order_by(Badge.points))).scalars().all()
        )
