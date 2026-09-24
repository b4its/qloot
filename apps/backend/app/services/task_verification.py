"""Task-completion verification against the underlying real-world event.

Tasks bound to a ``course_id`` or ``quest_id`` claim a specific action (finish
a lesson, attempt a quest) happened. Historically ``complete_task`` trusted the
caller unconditionally (pure self-report), so a student could farm OPT by
clicking "Selesaikan" without doing anything. This module checks the actual
event occurred before the reward is granted.

Tasks with neither ``course_id`` nor ``quest_id`` remain genuinely
honor-system (e.g. "read a chapter at home") — there is no event to check, so
self-report is the correct behaviour and is left unchanged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.models.learning import LessonProgress
from app.models.quest import QuestAttempt, Task


async def verify_task_completion(session: AsyncSession, task: Task, user_id: uuid.UUID) -> None:
    """Raise ``ConflictError`` if the task's bound event has not happened.

    - ``task.course_id`` set: the user must have completed at least one lesson
      in that course (any lesson, unless ``config.lesson_id`` names a specific
      one).
    - ``task.quest_id`` set: the user must have a valid ``QuestAttempt`` for
      that quest.
    - Neither set: no verification is possible or required (self-report).
    """
    lesson_id = None
    if task.config:
        raw = task.config.get("lesson_id")
        if raw:
            lesson_id = uuid.UUID(str(raw))

    if task.course_id is not None:
        stmt = select(LessonProgress.id).where(
            LessonProgress.user_id == user_id,
            LessonProgress.course_id == task.course_id,
            LessonProgress.completed.is_(True),
        )
        if lesson_id is not None:
            stmt = stmt.where(LessonProgress.lesson_id == lesson_id)
        found = (await session.execute(stmt.limit(1))).scalar_one_or_none()
        if found is None:
            raise ConflictError(
                "Selesaikan pelajaran yang terkait sebelum menyelesaikan tugas ini"
            )

    if task.quest_id is not None:
        stmt = select(QuestAttempt.id).where(
            QuestAttempt.quest_id == task.quest_id,
            QuestAttempt.user_id == user_id,
            QuestAttempt.is_valid.is_(True),
        )
        found = (await session.execute(stmt.limit(1))).scalar_one_or_none()
        if found is None:
            raise ConflictError("Ikuti quest yang terkait sebelum menyelesaikan tugas ini")
