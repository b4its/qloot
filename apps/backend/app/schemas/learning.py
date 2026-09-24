"""Course & lesson schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CourseCreate(BaseModel):
    """Create a subject ("pelajaran") for a class.

    `class_code` is the target class (e.g. "1A"). `class_type` is the optional
    programme (e.g. "IPA"). `subject` is the subject label (e.g. "Matematika").
    """

    title: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    cover_url: str | None = None
    subject: str | None = Field(default=None, max_length=128)
    class_code: str = Field(min_length=1, max_length=16)
    class_type: str | None = Field(default=None, max_length=32)
    is_published: bool = True


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    cover_url: str | None = None
    is_published: bool | None = None
    subject: str | None = Field(default=None, max_length=128)
    class_code: str | None = Field(default=None, max_length=16)
    class_type: str | None = Field(default=None, max_length=32)


class CourseOut(ORMModel):
    id: uuid.UUID
    title: str
    slug: str
    description: str | None
    owner_id: uuid.UUID
    is_published: bool
    cover_url: str | None
    subject: str | None = None
    class_code: str | None = None
    class_type: str | None = None
    owner_name: str | None = None
    lesson_count: int = 0
    created_at: datetime
    updated_at: datetime


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content_md: str | None = None
    video_url: str | None = None
    position: int = 0
    # Lessons are published on creation by default (matches CourseCreate); set
    # false explicitly to stage a draft.
    is_published: bool = True


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_md: str | None = None
    video_url: str | None = None
    position: int | None = None
    is_published: bool | None = None


class LessonReorder(BaseModel):
    """A full, explicit lesson order to rewrite positions from."""

    lesson_ids: list[uuid.UUID] = Field(min_length=1)


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
