"""Room service: rooms, members, events."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.identity import User
from app.models.room import Room, RoomEvent, RoomInvitation, RoomMember


def generate_room_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class RoomService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, owner: User, **data) -> Room:
        code = generate_room_code()
        while (
            await self.session.execute(select(Room).where(Room.code == code))
        ).scalar_one_or_none():
            code = generate_room_code()
        room = Room(owner_id=owner.id, code=code, **data)
        self.session.add(room)
        await self.session.flush()
        self.session.add(RoomMember(room_id=room.id, user_id=owner.id, role="teacher"))
        await self.session.flush()
        return room

    async def get(self, room_id: uuid.UUID) -> Room:
        room = await self.session.get(Room, room_id)
        if room is None:
            raise NotFoundError("Room not found")
        return room

    async def is_member(self, room_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        row = (
            await self.session.execute(
                select(RoomMember.id).where(
                    RoomMember.room_id == room_id, RoomMember.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return row is not None

    async def get_visible(self, room_id: uuid.UUID, user: User) -> Room:
        """Return a room the caller is allowed to read, else raise 404.

        Admins see anything, the owner sees their own room, members see rooms
        they belong to, and everyone else may read only **public** rooms. A
        hidden room 404s (never 403) so its existence is not leaked.
        """
        room = await self.get(room_id)
        if user.has_role("admin") or room.owner_id == user.id or room.is_public:
            return room
        if await self.is_member(room_id, user.id):
            return room
        raise NotFoundError("Room not found")

    async def get_by_code(self, code: str) -> Room:
        room = (
            await self.session.execute(select(Room).where(Room.code == code.upper()))
        ).scalar_one_or_none()
        if room is None:
            raise NotFoundError("Room not found")
        return room

    async def list_all(self, user: User, *, limit: int = 50, offset: int = 0) -> list[Room]:
        stmt = select(Room).order_by(Room.created_at.desc()).limit(limit).offset(offset)
        if not user.has_role("teacher", "admin"):
            stmt = stmt.where(Room.is_public.is_(True))
        else:
            stmt = stmt.where(Room.owner_id == user.id) if not user.has_role("admin") else stmt
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(self, room_id: uuid.UUID, user: User, **data) -> Room:
        room = await self._owned(room_id, user)
        for k, v in data.items():
            if v is not None:
                setattr(room, k, v)
        await self.session.flush()
        return room

    async def delete(self, room_id: uuid.UUID, user: User) -> None:
        """Delete a room (owner or admin); cascades members/events."""
        room = await self._owned(room_id, user)
        await self.session.delete(room)
        await self.session.flush()

    async def open(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self._owned(room_id, user)
        room.status = "open"
        room.opens_at = room.opens_at or datetime.now(UTC)
        await self._emit(room.id, "opened", {"by": str(user.id)})
        await self.session.flush()
        await self._notify_members(room, "Ruang dibuka", f"Ruang '{room.name}' sudah dibuka.")
        return room

    async def close(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self._owned(room_id, user)
        room.status = "closed"
        room.closes_at = datetime.now(UTC)
        await self._emit(room.id, "closed", {"by": str(user.id)})
        await self.session.flush()
        return room

    async def lock(self, room_id: uuid.UUID, user: User) -> Room:
        """Freeze new joins while the room stays open (GAME-08).

        Existing members can keep participating (answering, chatting via the
        WS ``signal`` passthrough); only ``join``/``join-by-code`` are
        blocked while locked.
        """
        room = await self._owned(room_id, user)
        if room.status != "open":
            raise ConflictError("Only an open room can be locked")
        room.is_locked = True
        await self._emit(room.id, "locked", {"by": str(user.id)})
        await self.session.flush()
        return room

    async def unlock(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self._owned(room_id, user)
        room.is_locked = False
        await self._emit(room.id, "unlocked", {"by": str(user.id)})
        await self.session.flush()
        return room

    async def join(self, room_id: uuid.UUID, user: User) -> RoomMember:
        room = await self.get(room_id)
        if room.status in ("closed", "archived"):
            raise ConflictError("Room is closed")
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user.id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is None:
            if room.is_locked:
                raise ConflictError("Room is locked to new participants")
            # Lock the room row so concurrent joins can't exceed capacity.
            await self.session.execute(select(Room.id).where(Room.id == room_id).with_for_update())
            count = len(await self.participants(room_id))
            if count >= room.max_participants:
                raise ConflictError("Room is full")
            member = RoomMember(room_id=room_id, user_id=user.id, role="student")
            self.session.add(member)
            await self.session.flush()

            # Badge: joining your 5th distinct room.
            from app.services.social_service import BadgeService

            joined = len(
                (
                    await self.session.execute(
                        select(RoomMember.id).where(RoomMember.user_id == user.id)
                    )
                )
                .scalars()
                .all()
            )
            if joined >= 5:
                await BadgeService(self.session).award(user=user, code="room_regular")
        else:
            member.is_present = True
            member.left_at = None
        await self._emit(room_id, "joined", {"user_id": str(user.id)})
        await self.session.flush()
        return member

    async def leave(self, room_id: uuid.UUID, user: User) -> None:
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user.id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is not None:
            member.is_present = False
            member.left_at = datetime.now(UTC)
            await self._emit(room_id, "left", {"user_id": str(user.id)})
            await self.session.flush()

    async def mark_present(self, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Flip ``is_present`` on WS connect, without the HTTP ``join`` side
        effects (badge, capacity check, joined-event). A user must already be
        a member (or owner) to have reached the socket in the first place.
        """
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user_id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is not None:
            member.is_present = True
            member.left_at = None
            await self.session.flush()

    async def mark_absent(self, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Flip ``is_present`` off on WS disconnect (last socket for this
        user/room only — callers must have already checked the connection
        count reached zero).
        """
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user_id
        )
        member = (await self.session.execute(stmt)).scalar_one_or_none()
        if member is not None:
            member.is_present = False
            member.left_at = datetime.now(UTC)
            await self.session.flush()

    async def participants(
        self, room_id: uuid.UUID, *, limit: int = 200, offset: int = 0
    ) -> list[tuple[RoomMember, str | None]]:
        """Room members joined with their display name (never N+1)."""
        stmt = (
            select(RoomMember, User.full_name)
            .join(User, User.id == RoomMember.user_id)
            .where(RoomMember.room_id == room_id)
            .order_by(RoomMember.joined_at)
            .limit(limit)
            .offset(offset)
        )
        return [(m, name) for m, name in (await self.session.execute(stmt)).all()]

    async def live_leaderboard(
        self, room_id: uuid.UUID, *, limit: int = 200, offset: int = 0
    ) -> list[dict]:
        """Ranking of room members by best exam score in this room.

        Includes every member (each row carries ``is_present`` so the UI can
        distinguish present from away) — the score still comes only from exams
        attached to this room.
        """
        from sqlalchemy import func
        from sqlalchemy import select as _select

        from app.models.exam import Exam, ExamAttempt

        room_exams = _select(Exam.id).where(Exam.room_id == room_id).scalar_subquery()
        best = (
            _select(
                ExamAttempt.user_id.label("user_id"),
                func.max(ExamAttempt.score_bp).label("best"),
            )
            .where(ExamAttempt.score_bp.is_not(None))
            .where(ExamAttempt.exam_id.in_(room_exams))
            .group_by(ExamAttempt.user_id, ExamAttempt.exam_id)
            .subquery()
        )
        totals = (
            _select(
                best.c.user_id.label("user_id"),
                func.coalesce(func.sum(best.c.best), 0).label("score"),
            )
            .group_by(best.c.user_id)
            .subquery()
        )
        stmt = (
            _select(
                RoomMember.user_id,
                User.full_name,
                RoomMember.is_present,
                func.coalesce(totals.c.score, 0).label("score"),
            )
            .join(User, User.id == RoomMember.user_id)
            .outerjoin(totals, totals.c.user_id == RoomMember.user_id)
            .where(RoomMember.room_id == room_id)
            # Hide deactivated members so this board matches /rankings/rooms/{id}.
            .where(User.is_active.is_(True))
            .order_by(func.coalesce(totals.c.score, 0).desc(), RoomMember.user_id.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "rank": i + 1,
                "user_id": r.user_id,
                "display_name": r.full_name,
                "score_bp": int(r.score or 0),
                "is_present": r.is_present,
            }
            for i, r in enumerate(rows)
        ]

    async def recent_events(
        self, room_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[RoomEvent]:
        stmt = (
            select(RoomEvent)
            .where(RoomEvent.room_id == room_id)
            .order_by(RoomEvent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def invite(
        self, room_id: uuid.UUID, user: User, *, email: str | None, note: str | None
    ) -> RoomInvitation:
        room = await self._owned(room_id, user)
        inv = RoomInvitation(room_id=room.id, email=email, note=note, code=generate_room_code(8))
        self.session.add(inv)
        await self._emit(room.id, "invited", {"email": email})
        await self.session.flush()
        # If the invited email belongs to a registered user, notify them
        # (kind "room") with the invite code.
        if email:
            from app.services.social_service import NotificationService

            invitee = (
                await self.session.execute(select(User).where(User.email == email.lower()))
            ).scalar_one_or_none()
            if invitee is not None:
                await NotificationService(self.session).notify(
                    user_id=invitee.id,
                    kind="room",
                    title=f"Undangan ke '{room.name}'",
                    body="Kamu diundang ke ruang. Gunakan kode undangan untuk bergabung.",
                    data={"room_id": str(room.id), "code": inv.code},
                )
        return inv

    async def _notify_members(self, room: Room, title: str, body: str) -> None:
        """Best-effort notification to every member of a room (kind 'room')."""
        from app.services.social_service import NotificationService

        member_ids = list(
            (
                await self.session.execute(
                    select(RoomMember.user_id).where(RoomMember.room_id == room.id)
                )
            )
            .scalars()
            .all()
        )
        if member_ids:
            await NotificationService(self.session).notify_many(
                user_ids=member_ids,
                kind="room",
                title=title,
                body=body,
                data={"room_id": str(room.id)},
            )

    async def accept_invite(self, code: str, user: User) -> RoomMember:
        inv = (
            await self.session.execute(
                select(RoomInvitation).where(RoomInvitation.code == code.upper())
            )
        ).scalar_one_or_none()
        if inv is None:
            raise NotFoundError("Invitation not found")
        if inv.accepted_at is None:
            inv.accepted_at = datetime.now(UTC)
            inv.user_id = user.id
        return await self.join(inv.room_id, user)

    async def _emit(self, room_id: uuid.UUID, event_type: str, payload: dict) -> None:
        self.session.add(RoomEvent(room_id=room_id, event_type=event_type, payload=payload))

    async def _owned(self, room_id: uuid.UUID, user: User) -> Room:
        room = await self.get(room_id)
        if not user.has_role("admin") and room.owner_id != user.id:
            raise ForbiddenError("You do not own this room")
        return room
