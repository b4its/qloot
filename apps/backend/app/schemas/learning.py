"""Course & lesson schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    cover_url: str | None = None


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    cover_url: str | None = None
    is_published: bool | None = None


class CourseOut(ORMModel):
    id: uuid.UUID
    title: str
    slug: str
    description: str | None
    owner_id: uuid.UUID
    is_published: bool
    cover_url: str | None
    created_at: datetime
    updated_at: datetime


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content_md: str | None = None
    video_url: str | None = None
    position: int = 0


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_md: str | None = None
    video_url: str | None = None
    position: int | None = None
    is_published: bool | None = None


class LessonOut(ORMModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    content_md: str | None
    video_url: str | None
    position: int
    is_published: bool
    created_at: datetime
    updated_at: datetime


class ProgressUpdate(BaseModel):
    progress_percent: int = Field(ge=0, le=100)
    completed: bool = False


class ProgressOut(ORMModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    course_id: uuid.UUID
    progress_percent: int
    completed: bool
    completed_at: datetime | None
