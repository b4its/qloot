"""Teacher analytics & submissions endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.api.deps import DbSession, LimitParam, OffsetParam, TeacherUser
from app.models.exam import Exam, ExamAttempt, Question, QuestionOption, StudentAnswer
from app.models.identity import User
from app.models.quest import Quest, QuestWinner
from app.models.wallet import RewardAllocation

router = APIRouter()


@router.get("/teacher/submissions")
async def submissions(
    user: TeacherUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    """Recent student answers across this teacher's exams, with AI feedback.

    Each row tells you *which student* answered, *which question*, their answer
    (option text for multiple-choice) and, for MC, whether it was correct.
    """
    stmt = (
        select(StudentAnswer, Question, ExamAttempt, Exam.title, User.full_name)
        .join(Question, Question.id == StudentAnswer.question_id)
        .join(ExamAttempt, ExamAttempt.id == StudentAnswer.attempt_id)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .join(User, User.id == ExamAttempt.user_id)
        .where(Exam.owner_id == user.id)
        .order_by(StudentAnswer.saved_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    # Resolve the chosen option text for multiple-choice answers in one query.
    mc_qids = {q.id for _sa, q, _a, _t, _n in rows if q.qtype == "multiple_choice"}
    option_text: dict[tuple[uuid.UUID, str], str] = {}
    if mc_qids:
        opt_rows = (
            await db.execute(
                select(QuestionOption.question_id, QuestionOption.label, QuestionOption.text).where(
                    QuestionOption.question_id.in_(mc_qids)
                )
            )
        ).all()
        option_text = {(qid, label): text for qid, label, text in opt_rows}

    def _is_correct(sa: StudentAnswer, q: Question) -> bool | None:
        if q.qtype != "multiple_choice" or sa.score_bp is None:
            return None
        return sa.score_bp >= sa.max_score_bp and sa.max_score_bp > 0

    return [
        {
            "answer_id": str(sa.id),
            "exam_id": str(attempt.exam_id),
            "exam_title": title,
            "attempt_id": str(attempt.id),
            "student_id": str(attempt.user_id),
            "student_name": name,
            "question_id": str(q.id),
            "qtype": q.qtype,
            "prompt": q.prompt,
            "answer_text": sa.answer_text,
            "answer_display": (
                option_text.get((q.id, (sa.answer_text or "").upper()))
                if q.qtype == "multiple_choice"
                else sa.answer_text
            ),
            "correct_answer": q.correct_answer if q.qtype == "multiple_choice" else None,
            "correct_display": (
                option_text.get((q.id, (q.correct_answer or "").upper()))
                if q.qtype == "multiple_choice"
                else None
            ),
            "is_correct": _is_correct(sa, q),
            "score_bp": sa.score_bp,
            "max_score_bp": sa.max_score_bp,
            "feedback": sa.feedback,
            "similarity_bp": sa.similarity_bp,
        }
        for sa, q, attempt, title, name in rows
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
