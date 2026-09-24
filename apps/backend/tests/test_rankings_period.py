"""Ranking period/season scoping (GAME-11): ?period=weekly|monthly|all.

Filters exam totals by ``ExamAttempt.submitted_at`` so a weekly/monthly board
only reflects recent activity, while ``all`` (default) stays lifetime —
unchanged from before this feature.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Exam, ExamAttempt, User

pytestmark = pytest.mark.integration


async def _user(session, email, role="student") -> User:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.security import hash_password
    from app.models.identity import Role, UserRole

    role_row = (await session.execute(select(Role).where(Role.name == role))).scalar_one()
    u = User(
        email=email,
        full_name=f"User {email}",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:64],
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role_row.id))
    await session.flush()
    return (
        await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .where(User.id == u.id)
        )
    ).scalar_one()


async def _graded(session, exam, user, score, submitted_at):
    a = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        attempt_number=1,
        status="graded",
        score_bp=score,
        passed=score >= 6000,
        started_at=submitted_at - timedelta(seconds=60),
        submitted_at=submitted_at,
        graded_at=submitted_at,
        duration_seconds=60,
    )
    session.add(a)
    await session.flush()
    return a


async def test_weekly_period_excludes_old_attempts(session):
    owner = await _user(session, "period_teacher@q.com", "teacher")
    exam = Exam(title="Period Exam", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    now = datetime.now(UTC)
    recent_student = await _user(session, "period_recent@q.com")
    old_student = await _user(session, "period_old@q.com")
    await _graded(session, exam, recent_student, 9000, now - timedelta(days=1))
    await _graded(session, exam, old_student, 8000, now - timedelta(days=40))
    await session.commit()

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_db
    from app.main import app

    sm = async_sessionmaker(session.bind, expire_on_commit=False)

    async def _override():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        from tests.helpers import register_actor

        await register_actor(c, "period_viewer@ex.com", "student")

        weekly = (await c.get("/api/v1/rankings/global?period=weekly")).json()
        weekly_ids = {e["user_id"] for e in weekly["entries"]}
        assert str(recent_student.id) in weekly_ids
        assert str(old_student.id) not in weekly_ids
        assert weekly["period"] == "weekly"

        lifetime = (await c.get("/api/v1/rankings/global?period=all")).json()
        lifetime_ids = {e["user_id"] for e in lifetime["entries"]}
        assert str(recent_student.id) in lifetime_ids
        assert str(old_student.id) in lifetime_ids
    app.dependency_overrides.clear()


async def test_monthly_period_includes_a_20_day_old_attempt_weekly_excludes_it(session):
    owner = await _user(session, "period_teacher2@q.com", "teacher")
    exam = Exam(title="Period Exam 2", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    now = datetime.now(UTC)
    student = await _user(session, "period_20d@q.com")
    await _graded(session, exam, student, 7000, now - timedelta(days=20))
    await session.commit()

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.session import get_db
    from app.main import app

    sm = async_sessionmaker(session.bind, expire_on_commit=False)

    async def _override():
        async with sm() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        from tests.helpers import register_actor

        await register_actor(c, "period_viewer2@ex.com", "student")

        weekly = (await c.get("/api/v1/rankings/global?period=weekly")).json()
        assert str(student.id) not in {e["user_id"] for e in weekly["entries"]}

        monthly = (await c.get("/api/v1/rankings/global?period=monthly")).json()
        assert str(student.id) in {e["user_id"] for e in monthly["entries"]}
    app.dependency_overrides.clear()


async def test_rankings_me_respects_period(client):
    from tests.helpers import register_actor

    await register_actor(client, "period_me@ex.com", "student")
    r = await client.get("/api/v1/rankings/me?period=weekly")
    assert r.status_code == 200, r.text
    assert r.json()["period"] == "weekly"

    r2 = await client.get("/api/v1/rankings/me")
    assert r2.status_code == 200
    assert r2.json()["period"] == "all"


async def test_invalid_period_value_is_rejected(client):
    from tests.helpers import register_actor

    await register_actor(client, "period_bad@ex.com", "student")
    r = await client.get("/api/v1/rankings/global?period=yearly")
    assert r.status_code == 422
