"""Community (social feed) endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.db.session import transaction
from app.schemas.common import Message
from app.schemas.community import (
    CommentCreate,
    CommentOut,
    CommunityStatsOut,
    PostCreate,
    PostDetailOut,
    PostOut,
    TopicOut,
)
from app.services.community_service import CommunityService

router = APIRouter(prefix="/community", tags=["community"])


@router.get("/posts", response_model=list[PostOut])
async def list_posts(
    user: CurrentUser, db: DbSession, topic: str | None = None, limit: int = 30, offset: int = 0
):
    return await CommunityService(db).list_posts(
        viewer_id=user.id, topic=topic, limit=limit, offset=offset
    )


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(payload: PostCreate, user: CurrentUser, db: DbSession):
    async with transaction(db):
        post = await CommunityService(db).create_post(user, body=payload.body, topic=payload.topic)
        return (await CommunityService(db)._decorate([post], user.id))[0]


@router.get("/posts/{post_id}", response_model=PostDetailOut)
async def get_post(post_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await CommunityService(db).get_post(post_id, user.id)


@router.delete("/posts/{post_id}", response_model=Message)
async def delete_post(post_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        await CommunityService(db).delete_post(user, post_id)
    return Message(message="Post deleted")


@router.post("/posts/{post_id}/like", response_model=PostOut)
async def toggle_like(post_id: uuid.UUID, user: CurrentUser, db: DbSession):
    async with transaction(db):
        service = CommunityService(db)
        post, _liked = await service.toggle_like(user, post_id)
        return (await service._decorate([post], user.id))[0]


@router.get("/posts/{post_id}/comments", response_model=list[CommentOut])
async def list_comments(post_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return await CommunityService(db).list_comments(post_id)


@router.post(
    "/posts/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
async def add_comment(post_id: uuid.UUID, payload: CommentCreate, user: CurrentUser, db: DbSession):
    async with transaction(db):
        comment = await CommunityService(db).add_comment(user, post_id, body=payload.body)
        return CommentOut(
            id=comment.id,
            author_id=comment.author_id,
            author_name=user.full_name,
            body=comment.body,
            created_at=comment.created_at,
        )


@router.get("/topics", response_model=list[TopicOut])
async def topics(user: CurrentUser, db: DbSession):
    return await CommunityService(db).topics()


@router.get("/stats", response_model=CommunityStatsOut)
async def stats(user: CurrentUser, db: DbSession):
    return await CommunityService(db).stats()
