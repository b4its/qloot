"""Badge progress: every catalogued badge exposes current/target toward unlock.

Progress must be derived from the *same* conditions that award the badge, so a
locked badge's bar can never disagree with the eventual award.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.social import Badge

pytestmark = pytest.mark.integration


async def _register(client, email, role="student"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name="Badge User")


async def test_badge_progress_endpoint_lists_every_catalogued_badge(client):
    await _register(client, "badge_progress@ex.com")
    r = await client.get("/api/v1/badges/progress")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) > 0
    for item in items:
        assert {"badge", "current", "target", "unlocked"} <= set(item)
        assert item["target"] >= 1
        assert 0 <= item["current"] <= item["target"]
        assert isinstance(item["unlocked"], bool)
    codes = {it["badge"]["code"] for it in items}
    # A fresh user has none of the activity badges, but every badge is listed.
    assert {"room_regular", "learner", "first_quest", "perfect_exam"} <= codes
    # And none are unlocked yet.
    assert all(not it["unlocked"] for it in items)


async def test_badge_progress_requires_auth(client):
    r = await client.get("/api/v1/badges/progress")
    assert r.status_code in (401, 403)


async def test_room_and_learner_progress_counts(session):
    from app.models.learning import Course, Lesson, LessonProgress
    from app.models.room import Room, RoomMember
    from tests.conftest import provision_user

    user = await provision_user(session, email=f"prog_{uuid.uuid4().hex[:8]}@ex.com")

    # 3 rooms joined (< 5) → room_regular locked at 3/5.
    for i in range(3):
        room = Room(
            id=uuid.uuid4(),
            name=f"Room {i}",
            code=f"R{uuid.uuid4().hex[:8]}",
            owner_id=user.id,
            status="open",
        )
        session.add(room)
        await session.flush()
        session.add(RoomMember(id=uuid.uuid4(), room_id=room.id, user_id=user.id))
    # 2 completed lessons (< 5) → learner locked at 2/5.
    course_id = uuid.uuid4()
    session.add(
        Course(
            id=course_id,
            title="C",
            slug=f"c-{uuid.uuid4().hex[:8]}",
            class_code="1A",
            class_type="IPA",
            owner_id=user.id,
        )
    )
    await session.flush()
    for i in range(2):
        lesson = Lesson(
            id=uuid.uuid4(), course_id=course_id, title=f"L{i}", position=i, is_published=True
        )
        session.add(lesson)
        await session.flush()
        session.add(
            LessonProgress(
                id=uuid.uuid4(),
                user_id=user.id,
                lesson_id=lesson.id,
                course_id=course_id,
                completed=True,
                progress_percent=100,
            )
        )
    await session.flush()

    from app.services.social_service import BadgeService

    items = await BadgeService(session).progress_for_user(user.id)
    by_code = {it["badge"].code: it for it in items}
    assert by_code["room_regular"]["current"] == 3
    assert by_code["room_regular"]["target"] == 5
    assert by_code["room_regular"]["unlocked"] is False
    assert by_code["learner"]["current"] == 2
    assert by_code["learner"]["target"] == 5
    assert by_code["learner"]["unlocked"] is False


async def test_awarded_badge_is_marked_unlocked(session):
    """A badge the user already holds reports unlocked even before the raw
    counter crosses the target (authoritative ownership wins).
    """
    from app.services.social_service import BadgeService
    from tests.conftest import provision_user

    user = await provision_user(session, email=f"owned_{uuid.uuid4().hex[:8]}@ex.com")

    badges = BadgeService(session)
    await badges.ensure_catalog()
    await badges.award(user=user, code="first_quest", notify=False)
    await session.flush()

    items = await badges.progress_for_user(user.id)
    by_code = {it["badge"].code: it for it in items}
    assert by_code["first_quest"]["unlocked"] is True


async def test_xp_milestone_progress_tracks_xp(session):
    """XP-milestone badges report the user's XP against the code's threshold,
    capped at the threshold.
    """
    from app.services.social_service import XP_MILESTONES, BadgeService
    from tests.conftest import provision_user

    user = await provision_user(session, email=f"xp_{uuid.uuid4().hex[:8]}@ex.com")

    items = await BadgeService(session).progress_for_user(user.id)
    by_code = {it["badge"].code: it for it in items}
    for threshold, code, *_ in XP_MILESTONES:
        assert by_code[code]["target"] == threshold
        assert by_code[code]["current"] == 0

    # Sanity: every milestone code appears in the catalog table too.
    codes = (await session.execute(select(Badge.code))).scalars().all()
    for _threshold, code, *_ in XP_MILESTONES:
        assert code in codes
