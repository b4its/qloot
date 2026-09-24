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
    ConsultationMessageIn,
    ConsultationMessageOut,
    ConsultationOut,
    ConsultationReschedule,
    CounselorOut,
    DashboardOut,
    GradeIn,
    GradeOut,
    GradeUpdate,
    MilestoneCreate,
    MilestoneOut,
    MilestoneUpdate,
    PendingReviewOut,
    PersonalityIn,
    PersonalityOut,
    RecommendationOut,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
    RoadmapReorder,
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


@router.put("/grades/{grade_id}", response_model=GradeOut)
async def update_grade(
    grade_id: uuid.UUID, payload: GradeUpdate, user: CurrentUser, db: DbSession
):
    """Edit one of the caller's grades (UIX-05)."""
    async with transaction(db):
        return await CareerService(db).update_grade(
            user.id, grade_id, grade=payload.grade, subject=payload.subject, term=payload.term
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


@router.post("/roadmap", response_model=MilestoneOut, status_code=201)
async def add_milestone(payload: MilestoneCreate, user: CurrentUser, db: DbSession):
    """Add a milestone to the caller's roadmap (CARE-05)."""
    async with transaction(db):
        return await CareerService(db).add_milestone(
            user.id,
            title=payload.title,
            description=payload.description,
            period=payload.period,
            tasks=payload.tasks,
        )


@router.post("/roadmap/reorder", response_model=list[MilestoneOut])
async def reorder_roadmap(payload: RoadmapReorder, user: CurrentUser, db: DbSession):
    """Atomically reorder the caller's milestones (CARE-05)."""
    async with transaction(db):
        return await CareerService(db).reorder_milestones(user.id, payload.ordered_ids)


@router.post("/roadmap/{milestone_id}/tasks/{task_index}/toggle", response_model=MilestoneOut)
async def toggle_milestone_task(
    milestone_id: uuid.UUID, task_index: int, user: CurrentUser, db: DbSession
):
    """Check/uncheck a task; progress is derived from completed tasks (CARE-05)."""
    async with transaction(db):
        return await CareerService(db).toggle_milestone_task(user.id, milestone_id, task_index)


@router.delete("/roadmap/{milestone_id}", response_model=Message)
async def delete_milestone(milestone_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        await CareerService(db).delete_milestone(user.id, milestone_id)
    return Message(message="Milestone deleted")


# --- consultations ---------------------------------------------------------
@router.get("/consultations", response_model=list[ConsultationOut])
async def list_consultations(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    return await CareerService(db).list_consultations(user.id, limit=limit, offset=offset)


@router.get("/counselors", response_model=list[CounselorOut])
async def counselors(user: CurrentUser, db: DbSession):
    """Real teachers/admins available as counselors (CARE-06)."""
    return [CounselorOut(**c) for c in await CareerService(db).list_available_counselors()]


@router.post("/consultations", response_model=ConsultationOut)
async def create_consultation(payload: ConsultationIn, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).create_consultation(
            user,
            counselor_user_id=payload.counselor_user_id,
            counselor=payload.counselor,
            topic=payload.topic,
            notes=payload.notes,
            scheduled_at=payload.scheduled_at,
        )


@router.post("/consultations/{consultation_id}/cancel", response_model=ConsultationOut)
async def cancel_consultation(consultation_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).cancel_consultation(user.id, consultation_id)


# --- counselor (BK) side ---------------------------------------------------
@router.get("/consultations/managed", response_model=list[ConsultationOut])
async def managed_consultations(
    teacher: TeacherUser,
    db: DbSession,
    status: str | None = None,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    """Consultations assigned to (or open for) the calling counselor (CARE-06)."""
    return await CareerService(db).list_counselor_consultations(
        teacher, status=status, limit=limit, offset=offset
    )


@router.post("/consultations/{consultation_id}/accept", response_model=ConsultationOut)
async def accept_consultation(consultation_id: uuid.UUID, teacher: TeacherUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).respond_consultation(teacher, consultation_id, "accept")


@router.post("/consultations/{consultation_id}/complete", response_model=ConsultationOut)
async def complete_consultation(consultation_id: uuid.UUID, teacher: TeacherUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).respond_consultation(teacher, consultation_id, "complete")


@router.post("/consultations/{consultation_id}/reschedule", response_model=ConsultationOut)
async def reschedule_consultation(
    consultation_id: uuid.UUID,
    payload: ConsultationReschedule,
    teacher: TeacherUser,
    db: DbSession,
):
    async with transaction(db):
        return await CareerService(db).reschedule_consultation(
            teacher, consultation_id, payload.scheduled_at
        )


@router.get(
    "/consultations/{consultation_id}/messages",
    response_model=list[ConsultationMessageOut],
)
async def consultation_messages(
    consultation_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: LimitParam = 200,
    offset: OffsetParam = 0,
):
    return await CareerService(db).list_consultation_messages(
        user, consultation_id, limit=limit, offset=offset
    )


@router.post(
    "/consultations/{consultation_id}/messages",
    response_model=ConsultationMessageOut,
    status_code=201,
)
async def post_consultation_message(
    consultation_id: uuid.UUID, payload: ConsultationMessageIn, user: CurrentUser, db: DbSession
):
    async with transaction(db):
        return await CareerService(db).add_consultation_message(
            user, consultation_id, payload.body
        )


# --- resource library ------------------------------------------------------
@router.get("/resources", response_model=list[ResourceOut])
async def resources(
    user: CurrentUser,
    db: DbSession,
    category: str | None = None,
    major: str | None = None,
    q: str | None = None,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    async with transaction(db):
        service = CareerService(db)
        await service.ensure_resources()
        return await service.list_resources(
            category, major, q=q, limit=limit, offset=offset
        )


@router.post("/resources", response_model=ResourceOut, status_code=201)
async def create_resource(payload: ResourceCreate, teacher: TeacherUser, db: DbSession):
    """Teacher/admin creates a resource-library entry (CARE-07)."""
    async with transaction(db):
        return await CareerService(db).create_resource(
            teacher,
            code=payload.code,
            category=payload.category,
            title=payload.title,
            description=payload.description,
            provider=payload.provider,
            is_free=payload.is_free,
            tags=payload.tags,
        )


@router.patch("/resources/{code}", response_model=ResourceOut)
async def update_resource(
    code: str, payload: ResourceUpdate, teacher: TeacherUser, db: DbSession
):
    async with transaction(db):
        return await CareerService(db).update_resource(
            teacher,
            code,
            title=payload.title,
            description=payload.description,
            provider=payload.provider,
            is_free=payload.is_free,
            tags=payload.tags,
        )


@router.delete("/resources/{code}", response_model=Message)
async def delete_resource(code: str, teacher: TeacherUser, db: DbSession):
    async with transaction(db):
        await CareerService(db).delete_resource(teacher, code)
    return Message(message="Resource deleted")


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


@router.post("/assistant/stream", dependencies=[Depends(rate_limit("ai"))])
async def assistant_stream(payload: ChatIn, user: CurrentUser, db: DbSession):
    """Stream the assistant reply as Server-Sent Events (CARE-04).

    Charges ORT up front (refunded if the request fails to start), then streams
    ``data:`` frames with the incremental text and a final ``event: done`` frame
    carrying the conversation id. The non-streaming ``/assistant`` endpoint
    remains the JSON fallback for clients that do not opt in.
    """
    import json as _json

    from fastapi.responses import StreamingResponse

    from app.db.session import session_factory
    from app.services.ai_usage_service import AiUsageService

    async with transaction(db):
        usage = AiUsageService(db)
        await usage.charge_request(user=user)

    async def _events():
        try:
            async with session_factory() as session:
                service = CareerService(session)
                async with session.begin():
                    async for chunk in service.assistant_reply_stream(
                        user, payload.message, conversation_id=payload.conversation_id
                    ):
                        yield f"data: {_json.dumps({'delta': chunk})}\n\n"
                last = service.last_conversation_id
                conv_id = str(last) if last else None
                yield f"event: done\ndata: {_json.dumps({'conversation_id': conv_id})}\n\n"
        except Exception as exc:  # noqa: BLE001 - surface, do not hang the stream
            yield f"event: error\ndata: {_json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
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
