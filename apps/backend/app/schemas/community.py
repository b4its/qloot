"""Community (social feed) schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    body: str = Field(min_length=2, max_length=2000)
    topic: str = Field(default="Umum", max_length=64)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class CommentOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    body: str
    hidden: bool = False
    created_at: datetime


class PostOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    handle: str
    topic: str
    body: str
    like_count: int
    comment_count: int
    liked_by_me: bool
    hidden: bool = False
    created_at: datetime


class PostDetailOut(PostOut):
    comments: list[CommentOut] = Field(default_factory=list)


class TopicOut(BaseModel):
    name: str
    posts: int


class CommunityStatsOut(BaseModel):
    members: int
    posts: int
    comments: int


class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(post|comment)$")
    target_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=255)


class ReportOut(BaseModel):
    id: uuid.UUID
    reporter_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    reason: str
    status: str
    body: str | None = None
    created_at: datetime


class ModerationAction(BaseModel):
    action: str = Field(pattern="^(hide|delete|dismiss)$")
    reason: str | None = Field(default=None, max_length=255)
