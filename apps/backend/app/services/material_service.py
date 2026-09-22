"""Material upload + AI question generation."""

from __future__ import annotations

import uuid

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import GenerationContext, QAContext, SummaryContext, get_ai_provider
from app.core.config import settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.exam import GradingJob, Question
from app.models.identity import User
from app.models.learning import LearningMaterial
from app.services.storage import build_key, sha256_hex, sniff_pdf, storage

log = get_logger("materials")


def extract_pdf_text(data: bytes) -> str:
    import io

    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages[:200]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("Could not read PDF content") from exc


class MaterialService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upload(
        self,
        owner: User,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        course_id: uuid.UUID | None = None,
        lesson_id: uuid.UUID | None = None,
    ) -> LearningMaterial:
        if len(content) > settings.ai_max_upload_bytes:
            raise ValidationError(f"File exceeds the {settings.ai_max_upload_bytes} byte limit")
        if not sniff_pdf(content):
            raise ValidationError("Only valid PDF files are accepted")

        key = build_key(owner.id, filename)
        storage.put(key, content, "application/pdf")
        text = extract_pdf_text(content)

        material = LearningMaterial(
            owner_id=owner.id,
            course_id=course_id,
            lesson_id=lesson_id,
            filename=filename,
            content_type="application/pdf",
            size_bytes=len(content),
            checksum_sha256=sha256_hex(content),
            storage_key=key,
            extracted_text=text[:500_000],
            status="ready",
        )
        self.session.add(material)
        await self.session.flush()
        log.info("material_uploaded", material_id=str(material.id), size=len(content))
        return material

    async def get(self, material_id: uuid.UUID) -> LearningMaterial:
        m = await self.session.get(LearningMaterial, material_id)
        if m is None:
            raise NotFoundError("Material not found")
        return m

    async def get_viewable(self, material_id: uuid.UUID, user: User) -> LearningMaterial:
        """Fetch a material only if the user is allowed to view it."""
        material = await self.get(material_id)
        await self._authorize_view(material, user)
        return material

    async def download(self, material_id: uuid.UUID, user: User) -> tuple[bytes, str, str]:
        """Return (bytes, filename, content_type) for an accessible material.

        Reuses the same view authorization as GET /materials/{id} (owner, admin
        or an enrolled course member), so uploaded PDFs are actually retrievable.
        """
        material = await self.get_viewable(material_id, user)
        data = storage.get(material.storage_key)
        return data, material.filename, material.content_type

    async def delete(self, material_id: uuid.UUID, user: User) -> None:
        """Delete a material (owner or admin) and its stored object."""
        material = await self.get(material_id)
        self._authorize(material, user)
        key = material.storage_key
        await self.session.delete(material)
        await self.session.flush()
        if key:
            storage.delete(key)

    async def update(
        self, material_id: uuid.UUID, user: User, *, filename: str
    ) -> LearningMaterial:
        """Rename a material (owner or admin). The PDF binary is immutable."""
        material = await self.get(material_id)
        self._authorize(material, user)
        material.filename = filename
        await self.session.flush()
        return material

    async def list_for_owner(
        self, user: User, *, limit: int = 100, offset: int = 0
    ) -> list[LearningMaterial]:
        """List the materials owned by the user (most recent first)."""
        from sqlalchemy import select

        stmt = (
            select(LearningMaterial)
            .where(LearningMaterial.owner_id == user.id)
            .order_by(LearningMaterial.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def enqueue_generation(
        self,
        material_id: uuid.UUID,
        user: User,
        *,
        count: int,
        language: str,
        exam_id: uuid.UUID | None,
    ) -> GradingJob:
        material = await self.get(material_id)
        self._authorize(material, user)
        # If questions will be attached to an exam, the caller must own it —
        # otherwise a teacher could inject AI questions into someone else's exam.
        if exam_id is not None:
            from app.models.exam import Exam

            exam = await self.session.get(Exam, exam_id)
            if exam is None:
                raise NotFoundError("Exam not found")
            if not user.has_role("admin") and exam.owner_id != user.id:
                raise ForbiddenError("You do not own this exam")
        job = GradingJob(
            owner_id=user.id,
            material_id=material.id,
            exam_id=exam_id,
            kind="generation",
            status="queued",
            payload={"count": count, "language": language},
        )
        self.session.add(job)
        await self.session.flush()
        log.info("generation_enqueued", job_id=str(job.id))
        return job

    async def run_generation(self, job: GradingJob) -> list[Question]:
        """Execute a generation job synchronously (called by the worker)."""
        material = await self.session.get(LearningMaterial, job.material_id)
        if material is None:
            raise NotFoundError("Material not found")
        # Without extracted text there is nothing to ground questions on; failing
        # loudly beats generating meaningless questions from an empty context.
        text = (material.extracted_text or "").strip()
        if len(text) < 20:
            raise ValidationError(
                "Materi belum memiliki teks yang cukup untuk membuat soal. "
                "Unggah PDF yang berisi teks."
            )
        provider = get_ai_provider()
        payload = job.payload or {}
        ctx = GenerationContext(
            text=text,
            count=int(payload.get("count", 5)),
            language=payload.get("language", "id"),
            title=material.filename,
        )
        result = await provider.generate_questions(ctx)

        created: list[Question] = []
        for i, q in enumerate(result.questions):
            question = Question(
                exam_id=job.exam_id,
                material_id=material.id,
                owner_id=job.owner_id,
                prompt=q.prompt,
                correct_answer=q.correct_answer,
                max_score_bp=min(q.max_score_bp, 10_000),
                position=i,
                source="ai",
                review_status="pending",  # teacher must review before publish
                ai_job_id=job.id,
            )
            self.session.add(question)
            created.append(question)
        await self.session.flush()
        return created

    async def summarize(
        self, material_id: uuid.UUID, user: User, *, language: str = "id", max_words: int = 120
    ):
        """AI summary of a material's text (owner, admin, or enrolled student)."""
        material = await self.get(material_id)
        await self._authorize_view(material, user)
        provider = get_ai_provider()
        return await provider.summarize(
            SummaryContext(
                text=material.extracted_text or "", language=language, max_words=max_words
            )
        )

    async def ask(self, material_id: uuid.UUID, user: User, *, question: str, language: str = "id"):
        """AI Q&A grounded on a material's text (owner, admin, or enrolled student)."""
        material = await self.get(material_id)
        await self._authorize_view(material, user)
        provider = get_ai_provider()
        return await provider.answer(
            QAContext(text=material.extracted_text or "", question=question, language=language)
        )

    def _authorize(self, material: LearningMaterial, user: User) -> None:
        if user.has_role("admin"):
            return
        if material.owner_id != user.id:
            raise ForbiddenError("You do not own this material")

    async def _authorize_view(self, material: LearningMaterial, user: User) -> None:
        """Owner, admin, or a member of the material's course may read it.

        Materials without a course are private to their owner (and admins).
        """
        if user.has_role("admin") or material.owner_id == user.id:
            return
        if material.course_id is not None and await self._is_course_member(
            material.course_id, user.id
        ):
            return
        raise ForbiddenError("You are not enrolled in this material's course")

    async def _is_course_member(self, course_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        from sqlalchemy import select

        from app.models.learning import CourseMember

        stmt = (
            select(CourseMember.id)
            .where(CourseMember.course_id == course_id, CourseMember.user_id == user_id)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
