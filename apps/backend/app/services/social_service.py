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
        """Idempotently seed the badge catalog and assign on-chain ids.

        Uses INSERT ... ON CONFLICT DO NOTHING so concurrent startups cannot
        race the `code` unique constraint.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        catalog = [
            ("first_quest", "First Quest", "Completed your first quest", "🎯", 10),
            ("quiz_master", "Quiz Master", "Completed 5 lessons", "🧠", 25),
            ("top_3", "Podium Finish", "Finished in the top 3 of a quest", "🥉", 50),
            ("first_reward", "First OPT", "Earned your first OryphemToken", "💎", 15),
            ("room_regular", "Room Regular", "Joined 5 rooms", "🎪", 20),
            ("perfect_exam", "Perfect Score", "Scored 100% on an exam", "🌟", 40),
            ("learner", "Dedicated Learner", "Completed 10 lessons", "📚", 30),
        ]
        rows = [
            {
                "code": code,
                "name": name,
                "description": desc,
                "icon": icon,
                "points": points,
            }
            for code, name, desc, icon, points in catalog
        ]
        await self.session.execute(
            pg_insert(Badge).values(rows).on_conflict_do_nothing(index_elements=["code"])
        )
        await self.session.flush()
        await self._assign_on_chain_ids()

    async def _assign_on_chain_ids(self) -> None:
        """Assign sequential on-chain badge ids (1..255) to unassigned badges."""
        rows = (
            (
                await self.session.execute(
                    select(Badge)
                    .where(Badge.on_chain_id.is_(None))
                    .order_by(Badge.points, Badge.code)
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return
        used = {
            b.on_chain_id
            for b in (
                await self.session.execute(select(Badge).where(Badge.on_chain_id.is_not(None)))
            )
            .scalars()
            .all()
        }
        next_id = 1
        assigned: list[Badge] = []
        for badge in rows:
            while next_id in used:
                next_id += 1
            if next_id > 255:
                # ERC-1155 badge ids are uint8; anything beyond is left without
                # an on-chain id. Log it instead of silently dropping.
                log.warning(
                    "badge_on_chain_id_capacity_reached",
                    pending=len(rows) - len(assigned),
                    cap=255,
                )
                break
            badge.on_chain_id = next_id
            used.add(next_id)
            assigned.append(badge)
        await self.session.flush()
        # NOTE: QLoot's on-chain contracts are pure ERC-1155 digital assets
        # (OPT/QTC/ORT); badges are tracked off-chain only, so there is no
        # on-chain badge registration/award step to enqueue here.

    async def award(
        self, *, user: User, code: str, meta: dict | None = None, notify: bool = True
    ) -> UserBadge | None:
        """Award a badge idempotently. Returns None if already owned."""
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
