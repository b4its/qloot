"""Gamification: ranking correctness and materialized leaderboards."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models import Exam, ExamAttempt, User
from app.services.leaderboard_service import LeaderboardService

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


async def _graded(session, exam, user, score, flagged=False):
    now = datetime.now(UTC)
    a = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        attempt_number=1,
        status="graded",
        score_bp=score,
        passed=score >= 6000,
        started_at=now - timedelta(seconds=60),
        submitted_at=now,
        graded_at=now,
        duration_seconds=60,
        is_flagged=flagged,
    )
    session.add(a)
    await session.flush()
    return a


async def test_materialize_global_leaderboard(session):
    owner = await _user(session, "lb_teacher@q.com", "teacher")
    exam = Exam(title="LB Exam", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()

    a = await _user(session, "lb_a@q.com")
    b = await _user(session, "lb_b@q.com")
    await _graded(session, exam, a, 9000)
    await _graded(session, exam, b, 7000)

    svc = LeaderboardService(session)
    n = await svc.materialize_global()
    assert n >= 2

    entries = await svc.get_materialized("global")
    # Ranks are contiguous and sorted by score desc (other tests' users may
    # also be present, so assert on structure + our two users' relative order).
    ranks = [e.rank for e in entries]
    assert ranks == sorted(ranks)
    scores = [e.score_bp for e in entries]
    assert scores == sorted(scores, reverse=True)
    by_user = {e.user_id: e for e in entries}
    assert by_user[a.id].score_bp == 9000
    assert by_user[b.id].score_bp == 7000
    assert by_user[a.id].rank < by_user[b.id].rank

    # Re-materializing replaces entries rather than appending.
    await svc.materialize_global()
    entries2 = await svc.get_materialized("global")
    assert len(entries2) == len(entries)


async def test_flagged_attempts_excluded_from_materialized_board(session):
    owner = await _user(session, "lb_t2@q.com", "teacher")
    exam = Exam(title="LB Exam 2", owner_id=owner.id, is_active=True)
    session.add(exam)
    await session.flush()
    u = await _user(session, "lb_flagged@q.com")
    await _graded(session, exam, u, 9999, flagged=True)

    svc = LeaderboardService(session)
    await svc.materialize_global()
    entries = await svc.get_materialized("global")
    assert all(e.user_id != u.id for e in entries)


async def test_global_ranking_excludes_zero_score_users(client):
    # A brand-new student with no attempts must not appear in the global board.
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rank_empty@ex.com",
            "full_name": "Empty",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert r.status_code == 201
    mid = r.json()["id"]
    board = await client.get("/api/v1/rankings/global")
    assert board.status_code == 200
    assert all(e["user_id"] != mid for e in board.json()["entries"])


async def test_personal_ranking_reports_position(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rank_me@ex.com",
            "full_name": "Rank Me",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert r.status_code == 201
    me = await client.get("/api/v1/rankings/me")
    assert me.status_code == 200
    body = me.json()
    # A fresh user still gets a concrete rank (>= 1).
    assert body["rank"] >= 1
    assert "total_score_bp" in body


async def test_streak_derivation_from_task_completions(session):
    """GAME-05: streaks are derived from real activity dates, never stored."""
    from app.models.quest import Task, TaskCompletion
    from app.services.gamification_service import GamificationService
    from app.services.keys import task_reward_key
    from app.services.reward_engine import RewardEngine

    student = await _user(session, "streak_a@q.com")
    task = Task(title="Daily", kind="daily", reward_amount=5, owner_id=None)
    session.add(task)
    await session.flush()

    engine = RewardEngine(session)
    now = datetime.now(UTC)
    for offset in (2, 1, 0):  # three consecutive days ending today
        day = now - timedelta(days=offset)
        rkey = task_reward_key(task.id, student.id, day.date().isoformat())
        session.add(
            TaskCompletion(
                task_id=task.id,
                user_id=student.id,
                period_key=day.date().isoformat(),
                reward_key=rkey,
                completed_at=day,
            )
        )
        await session.flush()
    await session.commit()

    result = await GamificationService(session).streak_for_user(student.id)
    assert result["current_streak"] == 3
    assert result["best_streak"] == 3
    assert result["last_active_date"] is not None
    _ = engine  # unused import guard for readability of the reward-key call


async def test_streak_breaks_on_a_gap_day(session):
    from app.models.quest import Task, TaskCompletion
    from app.services.gamification_service import GamificationService
    from app.services.keys import task_reward_key

    student = await _user(session, "streak_b@q.com")
    task = Task(title="Daily2", kind="daily", reward_amount=5, owner_id=None)
    session.add(task)
    await session.flush()

    now = datetime.now(UTC)
    # Active 4 and 3 days ago (a run of 2), then a gap, then active today.
    for offset in (4, 3, 0):
        day = now - timedelta(days=offset)
        rkey = task_reward_key(task.id, student.id, f"gap-{offset}")
        session.add(
            TaskCompletion(
                task_id=task.id,
                user_id=student.id,
                period_key=f"gap-{offset}",
                reward_key=rkey,
                completed_at=day,
            )
        )
        await session.flush()
    await session.commit()

    result = await GamificationService(session).streak_for_user(student.id)
    # Current streak only counts the unbroken run ending today (1 day).
    assert result["current_streak"] == 1
    # Best streak captures the earlier 2-day run.
    assert result["best_streak"] == 2


async def test_streak_is_zero_with_no_activity(session):
    from app.services.gamification_service import GamificationService

    student = await _user(session, "streak_c@q.com")
    result = await GamificationService(session).streak_for_user(student.id)
    assert result == {"current_streak": 0, "best_streak": 0, "last_active_date": None}


async def test_gamification_me_endpoint_includes_streak(client):
    from tests.helpers import register_actor

    await register_actor(client, "streak_endpoint@ex.com", "student")
    me = await client.get("/api/v1/gamification/me")
    assert me.status_code == 200, me.text
    body = me.json()
    assert "current_streak" in body
    assert "best_streak" in body
    assert body["current_streak"] == 0  # no activity yet
