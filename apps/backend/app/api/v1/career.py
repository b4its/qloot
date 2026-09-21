"""Career guidance endpoints: dashboard, personality, roadmap, BK, library, chat."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, TeacherUser
from app.db.session import transaction
from app.schemas.career import (
    ChatIn,
    ChatOut,
    ConsultationIn,
    ConsultationOut,
    DashboardOut,
    GradeIn,
    GradeOut,
    MilestoneOut,
    MilestoneUpdate,
    PersonalityIn,
    PersonalityOut,
    RecommendationOut,
    ResourceOut,
)
from app.schemas.common import Message
from app.services.career_service import CareerService

router = APIRouter(prefix="/career", tags=["career"])


# --- academic dashboard ----------------------------------------------------
@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(user: CurrentUser, db: DbSession):
    return await CareerService(db).dashboard(user)


@router.get("/grades", response_model=list[GradeOut])
async def list_grades(user: CurrentUser, db: DbSession):
    return await CareerService(db).list_grades(user.id)


@router.post("/grades", response_model=GradeOut)
async def upsert_grade(payload: GradeIn, user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).upsert_grade(
            user.id, payload.subject, payload.grade, payload.term
        )


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
async def list_recommendations(user: CurrentUser, db: DbSession):
    return await CareerService(db).list_recommendations(user.id)


@router.post("/recommendations/generate", response_model=list[RecommendationOut])
async def generate_recommendations(user: CurrentUser, db: DbSession):
    async with transaction(db):
        return await CareerService(db).generate_recommendations(user)


@router.post("/recommendations/submit", response_model=Message)
async def submit_for_review(user: CurrentUser, db: DbSession):
    async with transaction(db):
        n = await CareerService(db).submit_for_review(user)
    return Message(message=f"{n} recommendations submitted for review")


@router.post("/recommendations/approve", response_model=Message)
async def approve_recommendations(
    counselor: TeacherUser, db: DbSession, user_id: uuid.UUID | None = None
):
    """Approve a student's recommendations (counselor/teacher only).

    The human-in-the-loop design requires the *counselor* (guru BK) to approve,
    never the student themselves. ``user_id`` selects the student; it defaults
    to the caller only for a teacher reviewing their own preview.
    """
    async with transaction(db):
        target = user_id or counselor.id
        n = await CareerService(db).approve_user(target)
    return Message(message=f"{n} recommendations approved; roadmap activated")


@router.get("/roadmap", response_model=list[MilestoneOut])
async def roadmap(user: CurrentUser, db: DbSession):
    return await CareerService(db).list_milestones(user.id)


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
async def list_consultations(user: CurrentUser, db: DbSession):
    return await CareerService(db).list_consultations(user.id)


@router.get("/counselors", response_model=list[dict])
async def counselors(user: CurrentUser, db: DbSession):
    return CareerService(db).counselors()


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
):
    async with transaction(db):
        service = CareerService(db)
        await service.ensure_resources()
        return await service.list_resources(category, major)


# --- assistant -------------------------------------------------------------
@router.post("/assistant", response_model=ChatOut)
async def assistant(payload: ChatIn, user: CurrentUser, db: DbSession):
    reply = await CareerService(db).assistant_reply(user, payload.message)
    return ChatOut(answer=reply["answer"], confidence_bp=reply["confidence_bp"])
