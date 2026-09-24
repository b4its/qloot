"""Bulk seeder regression: quest_outcomes must respect QuestWinner constraints.

QuestWinner is unique on both (quest_id, user_id) and (quest_id, rank). The
bulk seeder originally deduped only on the former, so a second student could
be assigned an already-taken rank for the same quest — raising
"duplicate key value violates unique constraint uq_quest_winners_quest_rank"
and aborting `make db-seed`. These tests lock in the fix and idempotency.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.seed_bulk_extra import seed_quest_outcomes
from app.models import Exam, ExamAttempt, User
from app.models.quest import Quest, QuestRule, QuestWinner
from app.services.keys import reward_key

pytestmark = pytest.mark.integration


async def _student(session, email: str) -> User:
    from app.core.security import hash_password
    from app.models.identity import Role, UserRole

    role_row = (await session.execute(select(Role).where(Role.name == "student"))).scalar_one()
    u = User(
        email=email,
        full_name="Bulk User",
        password_hash=hash_password("Password123!"),
        chain_user_ref="0x" + (uuid.uuid4().hex + uuid.uuid4().hex)[:64],
    )
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role_row.id))
    await session.flush()
    return u


async def _quest_with_rule(session, teacher: User, n: int) -> Quest:
    quest = Quest(
        title=f"Bulk Quest {n}",
        description="seed regression",
        owner_id=teacher.id,
        status="closed",
    )
    session.add(quest)
    await session.flush()
    session.add(
        QuestRule(
            quest_id=quest.id,
            rank=1,
            reward_amount=100,
            min_score_bp=0,
        )
    )
    await session.flush()
    return quest


async def _attempt(session, exam: Exam, user: User, n: int) -> ExamAttempt:
    now = datetime.now(UTC)
    a = ExamAttempt(
        exam_id=exam.id,
        user_id=user.id,
        attempt_number=1,
        status="graded",
        score_bp=8000,
        passed=True,
        started_at=now - timedelta(minutes=10 + n),
        submitted_at=now - timedelta(minutes=5),
        graded_at=now,
        duration_seconds=600,
    )
    session.add(a)
    await session.flush()
    return a


async def _seed_fixtures(session, n_students: int = 6, n_quests: int = 3):
    teacher = await _student(session, f"bulk_teacher_{uuid.uuid4().hex[:6]}@ex.com")
    exam = Exam(title="Bulk Exam", owner_id=teacher.id, duration_minutes=20)
    session.add(exam)
    await session.flush()

    students = [
        await _student(session, f"bulk_s{i}_{uuid.uuid4().hex[:6]}@ex.com")
        for i in range(n_students)
    ]
    for i, s in enumerate(students):
        await _attempt(session, exam, s, i)
    quests = [await _quest_with_rule(session, teacher, i) for i in range(n_quests)]
    await session.flush()
    # Return the created fixtures (not just the students) so callers can scope
    # their assertions to *this* run — the test DB is shared across the suite.
    return students, exam, quests


async def test_seed_quest_outcomes_is_idempotent(session):
    students, _exam, quests = await _seed_fixtures(session)
    quest_ids = [q.id for q in quests]

    await seed_quest_outcomes(session, students)
    first = (
        (await session.execute(select(QuestWinner).where(QuestWinner.quest_id.in_(quest_ids))))
        .scalars()
        .all()
    )

    # A second pass must not raise uq_quest_winners_quest_rank / _user.
    await seed_quest_outcomes(session, students)
    second = (
        (await session.execute(select(QuestWinner).where(QuestWinner.quest_id.in_(quest_ids))))
        .scalars()
        .all()
    )

    assert len(second) == len(first)
    assert len(first) >= 1
    # Both uniqueness invariants hold across these quests' winners.
    assert len({(w.quest_id, w.user_id) for w in second}) == len(second)
    assert len({(w.quest_id, w.rank) for w in second}) == len(second)


async def test_seed_quest_outcomes_respects_preexisting_winners(session):
    students, exam, quests = await _seed_fixtures(session)
    quest = quests[0]
    attempt = (
        await session.execute(select(ExamAttempt).where(ExamAttempt.exam_id == exam.id).limit(1))
    ).scalar_one()

    # Pre-existing winner occupying (quest, rank=1).
    session.add(
        QuestWinner(
            id=uuid.uuid4(),
            quest_id=quest.id,
            user_id=students[0].id,
            rank=1,
            score_bp=9000,
            submitted_at=datetime.now(UTC),
            duration_seconds=500,
            attempt_id=attempt.id,
            reward_key=reward_key(quest.id, students[0].id, 1, 1),
        )
    )
    await session.flush()

    # Must skip the taken (quest, rank=1) instead of colliding with it.
    await seed_quest_outcomes(session, students)

    quest_ids = [q.id for q in quests]
    winners = (
        (await session.execute(select(QuestWinner).where(QuestWinner.quest_id.in_(quest_ids))))
        .scalars()
        .all()
    )
    ranks_for_quest = [w.rank for w in winners if w.quest_id == quest.id]
    assert ranks_for_quest.count(1) == 1
    assert len({(w.quest_id, w.rank) for w in winners}) == len(winners)


async def test_seed_career_covers_every_consultation_status(session):
    """CI-04: consultations must include completed (not just pending/cancelled),
    and recommendations a mix of draft/in_review/approved."""
    from app.db.seed_bulk import seed_career
    from app.db.seed_bulk_extra import seed_misc
    from app.models.career import CareerRecommendation, Consultation

    # A modest cohort is enough: the seeder pads to TARGET regardless.
    students = [await _student(session, f"carseed_{i}@ex.com") for i in range(8)]
    await session.flush()

    await seed_career(session, students)
    # Recommendations + consultation threads are seeded by seed_misc.
    await seed_misc(session, students, [])
    await session.flush()

    statuses = set(
        (await session.execute(select(Consultation.status))).scalars().all()
    )
    assert "completed" in statuses, f"consultation statuses missing 'completed': {statuses}"
    assert {"pending", "cancelled"} <= statuses

    rec_statuses = set(
        (await session.execute(select(CareerRecommendation.status))).scalars().all()
    )
    assert {"draft", "in_review", "approved"} <= rec_statuses
