"""Teacher analytics & submissions endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.api.deps import DbSession, LimitParam, OffsetParam, TeacherUser
from app.models.exam import Exam, ExamAttempt, Question, StudentAnswer
from app.models.quest import Quest, QuestWinner
from app.models.wallet import RewardAllocation

router = APIRouter()


@router.get("/teacher/submissions")
async def submissions(
    user: TeacherUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    """Recent student answers across this teacher's exams, with AI feedback."""
    stmt = (
        select(StudentAnswer, Question, ExamAttempt, Exam.title)
        .join(Question, Question.id == StudentAnswer.question_id)
        .join(ExamAttempt, ExamAttempt.id == StudentAnswer.attempt_id)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .where(Exam.owner_id == user.id)
        .order_by(StudentAnswer.saved_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "answer_id": str(sa.id),
            "exam_id": str(attempt.exam_id),
            "exam_title": title,
            "attempt_id": str(attempt.id),
            "student_id": str(attempt.user_id),
            "question_id": str(q.id),
            "prompt": q.prompt,
            "answer_text": sa.answer_text,
            "score_bp": sa.score_bp,
            "max_score_bp": sa.max_score_bp,
            "feedback": sa.feedback,
            "similarity_bp": sa.similarity_bp,
        }
        for sa, q, attempt, title in rows
    ]


@router.get("/teacher/analytics")
async def analytics(user: TeacherUser, db: DbSession):
    """Aggregate stats across this teacher's exams and quests."""
    exam_count = int(
        (
            await db.execute(select(func.count()).select_from(Exam).where(Exam.owner_id == user.id))
        ).scalar_one()
    )
    attempt_stats = (
        await db.execute(
            select(
                func.count(ExamAttempt.id),
                func.coalesce(func.avg(ExamAttempt.score_bp), 0),
                func.coalesce(
                    func.sum(case((ExamAttempt.passed.is_(True), 1), else_=0)),
                    0,
                ),
            )
            .join(Exam, Exam.id == ExamAttempt.exam_id)
            .where(Exam.owner_id == user.id, ExamAttempt.status == "graded")
        )
    ).one()
    attempt_count = int(attempt_stats[0] or 0)
    avg_score = int(attempt_stats[1] or 0)
    passed = int(attempt_stats[2] or 0)

    quest_count = int(
        (
            await db.execute(
                select(func.count()).select_from(Quest).where(Quest.owner_id == user.id)
            )
        ).scalar_one()
    )
    winners_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(QuestWinner)
                .join(Quest, Quest.id == QuestWinner.quest_id)
                .where(Quest.owner_id == user.id)
            )
        ).scalar_one()
    )
    opc_awarded = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(RewardAllocation.amount), 0))
                .join(Quest, Quest.id == RewardAllocation.quest_id)
                .where(Quest.owner_id == user.id)
            )
        ).scalar_one()
        or 0
    )

    return {
        "exams": exam_count,
        "graded_attempts": attempt_count,
        "average_score_bp": avg_score,
        "pass_rate_bp": int(round(passed * 10_000 / attempt_count)) if attempt_count else 0,
        "quests": quest_count,
        "winners": winners_count,
        "opc_awarded": opc_awarded,
    }
