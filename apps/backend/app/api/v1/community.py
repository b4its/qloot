"""Community (social feed) endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminUser, CurrentUser, DbSession, LimitParam, OffsetParam
from app.core.errors import ValidationError
from app.db.session import transaction
from app.schemas.common import Message
from app.schemas.community import (
    CommentCreate,
    CommentEdit,
    CommentOut,
    CommunityStatsOut,
    ModerationAction,
    PostCreate,
    PostDetailOut,
    PostOut,
    ReportCreate,
    ReportOut,
    TopicOut,
)
from app.services.audit import record as audit_record
from app.services.community_service import CommunityService

router = APIRouter(prefix="/community", tags=["community"])


@router.get("/posts", response_model=list[PostOut])
async def list_posts(
    user: CurrentUser,
    db: DbSession,
    topic: str | None = None,
    sort: str = "new",
    following: bool = False,
    limit: LimitParam = 30,
    offset: OffsetParam = 0,
):
    if sort not in ("new", "hot", "top"):
        raise ValidationError("sort must be new|hot|top")
    return await CommunityService(db).list_posts(
        viewer_id=user.id,
        topic=topic,
        sort=sort,
        following_only=following,
        limit=limit,
        offset=offset,
        include_hidden_for=user.id,
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
async def list_comments(
    post_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    return await CommunityService(db).list_comments(
        post_id, limit=limit, offset=offset, include_hidden_for=user.id
    )


@router.post(
    "/posts/{post_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
async def add_comment(post_id: uuid.UUID, payload: CommentCreate, user: CurrentUser, db: DbSession):
    async with transaction(db):
        comment = await CommunityService(db).add_comment(
            user, post_id, body=payload.body, parent_id=payload.parent_id
        )
        return CommentOut(
            id=comment.id,
            author_id=comment.author_id,
            author_name=user.full_name,
            body=comment.body,
            parent_id=comment.parent_id,
            edited_at=comment.edited_at,
            created_at=comment.created_at,
        )


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def edit_comment(
    comment_id: uuid.UUID, payload: CommentEdit, user: CurrentUser, db: DbSession
):
    """Edit your own comment; stamps ``edited_at`` (COMM-02)."""
    async with transaction(db):
        comment = await CommunityService(db).edit_comment(user, comment_id, body=payload.body)
        return CommentOut(
            id=comment.id,
            author_id=comment.author_id,
            author_name=user.full_name,
            body=comment.body,
            parent_id=comment.parent_id,
            edited_at=comment.edited_at,
            created_at=comment.created_at,
        )


@router.get("/topics", response_model=list[TopicOut])
async def topics(user: CurrentUser, db: DbSession):
    return await CommunityService(db).topics()


@router.delete("/comments/{comment_id}", response_model=Message)
async def delete_comment(comment_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Delete your own comment (or any, as an admin)."""
    async with transaction(db):
        await CommunityService(db).delete_comment(user, comment_id)
    return Message(message="Comment deleted")


@router.get("/stats", response_model=CommunityStatsOut)
async def stats(user: CurrentUser, db: DbSession):
    return await CommunityService(db).stats()


# --- reporting & moderation (COMM-01) -------------------------------------
@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def report_content(payload: ReportCreate, user: CurrentUser, db: DbSession):
    """Report a post or comment. One report per user per object."""
    async with transaction(db):
        rep = await CommunityService(db).report(
            user,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason,
        )
        return ReportOut(
            id=rep.id,
            reporter_id=rep.reporter_id,
            target_type=rep.target_type,
            target_id=rep.target_id,
            reason=rep.reason,
            status=rep.status,
            created_at=rep.created_at,
        )


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    admin: AdminUser,
    db: DbSession,
    status_filter: str | None = None,
    limit: LimitParam = 100,
    offset: OffsetParam = 0,
):
    """Admin moderation queue (paginated)."""
    rows = await CommunityService(db).list_reports(
        status=status_filter, limit=limit, offset=offset
    )
    return [ReportOut(**r) for r in rows]


@router.post("/reports/{report_id}/moderate", response_model=ReportOut)
async def moderate_report(
    report_id: uuid.UUID, payload: ModerationAction, admin: AdminUser, db: DbSession
):
    async with transaction(db):
        rep = await CommunityService(db).moderate(admin, report_id, payload.action)
        # Audit the moderation action (reason, when given, is recorded here).
        audit_record(
            db,
            actor_id=admin.id,
            action=f"community.{payload.action}",
            entity_type="community_report",
            entity_id=str(report_id),
            data={
                "target_type": rep.target_type,
                "target_id": str(rep.target_id),
                "reason": payload.reason,
            },
        )
        await db.flush()
        return ReportOut(
            id=rep.id,
            reporter_id=rep.reporter_id,
            target_type=rep.target_type,
            target_id=rep.target_id,
            reason=rep.reason,
            status=rep.status,
            created_at=rep.created_at,
        )
