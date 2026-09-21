"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    blockchain,
    career,
    certificates,
    community,
    courses,
    exams,
    health,
    materials,
    metrics,
    quests,
    rankings,
    rooms,
    social,
    tasks,
    teacher,
    wallet,
    ws,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(metrics.router, tags=["metrics"])
api_router.include_router(social.router, tags=["notifications", "badges"])
api_router.include_router(teacher.router, tags=["teacher"])
api_router.include_router(career.router)
api_router.include_router(certificates.router)
api_router.include_router(community.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(courses.router, tags=["learning"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(exams.router, tags=["exams"])
api_router.include_router(quests.router, prefix="/quests", tags=["quests"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(rankings.router, prefix="/rankings", tags=["rankings"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(blockchain.router, prefix="/blockchain", tags=["blockchain"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(ws.router, tags=["ws"])
