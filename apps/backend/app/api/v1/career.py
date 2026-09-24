"""Career guidance endpoints: dashboard, personality, roadmap, BK, library, chat."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, TeacherUser
from app.db.session import transaction
from app.middleware.rate_limit import rate_limit
from app.schemas.career import (
    AssistantConversationDetailOut,
    AssistantConversationOut,
    AssistantMessageOut,
    ChatIn,
    ChatOut,
    ConsultationIn,
    ConsultationOut,
    CounselorOut,
    DashboardOut,
    GradeIn,
    GradeOut,
    MilestoneOut,
    MilestoneUpdate,
    PendingReviewOut,
    PersonalityIn,
    PersonalityOut,
    RecommendationOut,
    ResourceOut,
)
from app.schemas.common import Message
from app.services.career_service import CareerService
from app.services.reward_engine import RewardEngine

router = APIRouter(prefix="/career", tags=["career"])


# --- academic dashboard ----------------------------------------------------
@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(user: CurrentUser, db: DbSession):
    return await CareerService(db).dashboard(user)


@router.get("/grades", response_model=list[GradeOut])
async def list_grades(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await CareerService(db).list_grades(user.id, limit=limit, offset=offset)


@router.post("/grades", response_model=GradeOut)
async def upsert_grade(payload: GradeIn, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).upsert_grade(
            user.id, payload.subject, payload.grade, payload.term
        )


@router.delete("/grades/{grade_id}", response_model=Message)
async def delete_grade(grade_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Remove one of your own academic grades."""
    async with transaction(db):
        await CareerService(db).delete_grade(user.id, grade_id)
    return Message(message="Grade deleted")


# --- personality -----------------------------------------------------------
@router.get("/personality", response_model=PersonalityOut | None)
async def get_personality(user: CurrentUser, db: DbSession):
    return await CareerService(db).latest_personality(user.id)


@router.post("/personality", response_model=PersonalityOut)
async def submit_personality(payload: PersonalityIn, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).score_personality(user, payload.answers)


# --- recommendations + roadmap --------------------------------------------
@router.get("/recommendations", response_model=list[RecommendationOut])
async def list_recommendations(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await CareerService(db).list_recommendations(user.id, limit=limit, offset=offset)


@router.post("/recommendations/generate", response_model=list[RecommendationOut])
async def generate_recommendations(user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).generate_recommendations(user)


@router.post("/recommendations/submit", response_model=Message)
async def submit_for_review(user: CurrentUser, db: DbSession):
    async with transaction(db):
        n = await CareerService(db).submit_for_review(user)
    return Message(message=f"{n} recommendations submitted for review")


@router.get("/recommendations/pending", response_model=list[PendingReviewOut])
async def pending_recommendations(
    counselor: TeacherUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """Students whose study-path plan awaits the counselor's approval."""
    rows = await CareerService(db).pending_review(limit=limit, offset=offset)
    return [
        PendingReviewOut(user_id=uid, display_name=name, top_major=major, count=n)
        for uid, name, major, n in rows
    ]


@router.post("/recommendations/approve", response_model=Message)
async def approve_recommendations(
    counselor: TeacherUser, db: DbSession, user_id: uuid.UUID | None = None
):
    """Approve a student's recommendations (counselor/teacher only).

    The human-in-the-loop design requires the *counselor* (guru BK) to approve,
    never the student themselves. ``user_id`` selects the student; it defaults
    to the caller only for a teacher previewing their own plan.

    The target must be the caller themselves or an actual student account — a
    teacher may not approve an arbitrary (or non-student) user by id.
    """
    from app.core.errors import ForbiddenError, NotFoundError
    from app.models.identity import User

    async with transaction(db):
        target_id = user_id or counselor.id
        target = await db.get(User, target_id)
        if target is None:
            raise NotFoundError("User not found")
        if target.id != counselor.id and not target.has_role("student"):
            raise ForbiddenError("Only a student's plan can be approved")
        n = await CareerService(db).approve_user(target_id)
    return Message(message=f"{n} recommendations approved; roadmap activated")


@router.get("/roadmap", response_model=list[MilestoneOut])
async def roadmap(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await CareerService(db).list_milestones(user.id, limit=limit, offset=offset)


@router.patch("/roadmap/{milestone_id}", response_model=MilestoneOut)
async def update_milestone(
    milestone_id: uuid.UUID, payload: MilestoneUpdate, user: CurrentUser, db: DbSession
):
    async with transaction(db):
        return await CareerService(db).update_milestone(
            user.id, milestone_id, payload.progress_percent
        )


# --- consultations ---------------------------------------------------------
@router.get("/consultations", response_model=list[ConsultationOut])
async def list_consultations(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await CareerService(db).list_consultations(user.id, limit=limit, offset=offset)


@router.get("/counselors", response_model=list[CounselorOut])
async def counselors(user: CurrentUser, db: DbSession):
    return [CounselorOut(**c) for c in CareerService(db).counselors()]


@router.post("/consultations", response_model=ConsultationOut)
async def create_consultation(payload: ConsultationIn, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).create_consultation(
            user, counselor=payload.counselor, topic=payload.topic, notes=payload.notes
        )


@router.post("/consultations/{consultation_id}/cancel", response_model=ConsultationOut)
async def cancel_consultation(consultation_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).cancel_consultation(user.id, consultation_id)


# --- resource library ------------------------------------------------------
@router.get("/resources", response_model=list[ResourceOut])
async def resources(
    user: CurrentUser,
    db: DbSession,
    category: str | None = None,
    major: str | None = None,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    async with transaction(db):
        service = CareerService(db)
        await service.ensure_resources()
        return await service.list_resources(category, major, limit=limit, offset=offset)


# --- assistant -------------------------------------------------------------
@router.post("/assistant", response_model=ChatOut, dependencies=[Depends(rate_limit("ai"))])
async def assistant(payload: ChatIn, user: CurrentUser, db: DbSession):
    """Answer a study/career question. Costs 1 ORT (or a free-tier slot)."""
    from app.services.ai_usage_service import AiUsageService

    async with transaction(db):
        usage = AiUsageService(db)
        ref = await usage.charge_request(user=user)
        try:
            reply = await CareerService(db).assistant_reply(
                user, payload.message, conversation_id=payload.conversation_id
            )
        except Exception:
            # Never charge for a failed request.
            await usage.refund_job(user_id=user.id, job_id=ref)
            raise
        ort_balance = await RewardEngine(db).asset_balance(user.id, "ORT")
        free_remaining = await usage.free_requests_remaining(user.id)
    return ChatOut(
        answer=reply["answer"],
        confidence_bp=reply["confidence_bp"],
        ort_balance=ort_balance,
        free_requests_remaining=free_remaining,
        conversation_id=reply.get("conversation_id"),
    )


# --- assistant history -----------------------------------------------------
@router.get("/assistant/conversations", response_model=list[AssistantConversationOut])
async def list_assistant_conversations(
    user: CurrentUser, db: DbSession, limit: LimitParam = 50, offset: OffsetParam = 0
):
    """The caller's assistant conversations, most recently active first."""
    rows = await CareerService(db).list_conversations(user.id, limit=limit, offset=offset)
    return [AssistantConversationOut.model_validate(r) for r in rows]


@router.get(
    "/assistant/conversations/{conversation_id}",
    response_model=AssistantConversationDetailOut,
)
async def get_assistant_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
):
    conv, messages = await CareerService(db).get_conversation(user.id, conversation_id)
    detail = AssistantConversationDetailOut.model_validate(conv)
    detail.messages = [AssistantMessageOut.model_validate(m) for m in messages]
    return detail


@router.delete("/assistant/conversations/{conversation_id}", response_model=Message)
async def delete_assistant_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
):
    async with transaction(db):
        await CareerService(db).delete_conversation(user.id, conversation_id)
    return Message(message="Conversation deleted")
