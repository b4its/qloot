"""Material upload + AI question generation."""

from __future__ import annotations

import uuid

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import (
    GenerationContext,
    QAContext,
    SummaryContext,
    cosine_similarity,
    get_ai_provider,
)
from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.exam import GradingJob, Question
from app.models.identity import User
from app.models.learning import LearningMaterial, MaterialChunk
from app.services.storage import build_key, scan_for_viruses, sha256_hex, sniff_pdf, storage

log = get_logger("materials")


def _chunk_text(text: str, *, size: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into overlapping character chunks on word boundaries.

    Deterministic and provider-agnostic: chunks are stable for the same input,
    so the RAG index is reproducible.
    """
    text = text.strip()
    if not text:
        return []
    size = max(200, size)
    overlap = max(0, min(overlap, size // 2))
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        # Prefer to break on the last whitespace within the window.
        if end < n and " " in text[start:end]:
            end = start + text.rfind(" ", start, end)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


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


def ocr_pdf(data: bytes) -> str:
    """Optional OCR fallback for scanned PDFs.

    Only runs when ``settings.material_ocr_enabled`` is set and the optional
    dependencies (tesseract + pdf2image) are importable. Returns "" when OCR is
    unavailable so the caller marks the material ``empty`` instead of failing.
    """
    if not settings.material_ocr_enabled:
        return ""
    try:
        import pytesseract  # type: ignore[import-not-found]
        from pdf2image import convert_from_bytes  # type: ignore[import-not-found]

        images = convert_from_bytes(data, dpi=200)
        return "\n".join(pytesseract.image_to_string(img) for img in images)
    except Exception as exc:  # noqa: BLE001 - OCR is best-effort
        log.warning("ocr_failed", error=str(exc))
        return ""



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
        # AV policy hook (documented no-op by default; see storage.scan_for_viruses).
        if not scan_for_viruses(content):
            raise ValidationError("Uploaded file rejected by the antivirus scan")

        key = build_key(owner.id, filename)
        storage.put(key, content, "application/pdf")
        text = extract_pdf_text(content)
        # Signal extraction quality at upload time: a scanned PDF yields (almost)
        # no text, so warn immediately instead of failing late in generation.
        extraction_status = "ok"
        if len(text.strip()) < settings.material_min_text_chars:
            ocr_text = ocr_pdf(content)
            if len(ocr_text.strip()) >= settings.material_min_text_chars:
                text = ocr_text
                extraction_status = "ocr"
            else:
                extraction_status = "empty"

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
            extraction_status=extraction_status,
        )
        self.session.add(material)
        await self.session.flush()
        # Build the RAG index (chunks + embeddings) so summary/Q&A can retrieve
        # relevant passages instead of truncating the document.
        await self._index_material(material)
        log.info("material_uploaded", material_id=str(material.id), size=len(content))
        return material

    async def _index_material(self, material: LearningMaterial) -> int:
        """Chunk the extracted text and store an embedding per chunk.

        Idempotent: any existing chunks are replaced. Returns the chunk count.
        """
        from sqlalchemy import delete

        text = (material.extracted_text or "").strip()
        await self.session.execute(
            delete(MaterialChunk).where(MaterialChunk.material_id == material.id)
        )
        if not text:
            await self.session.flush()
            return 0
        chunks = _chunk_text(text, size=settings.material_chunk_chars)
        try:
            vectors = await get_ai_provider().embed(chunks)
        except Exception as exc:  # noqa: BLE001 - retrieval degrades, upload works
            log.warning("material_embedding_failed", material_id=str(material.id), error=str(exc))
            vectors = [None] * len(chunks)  # type: ignore[list-item]
        for i, chunk in enumerate(chunks):
            self.session.add(
                MaterialChunk(
                    material_id=material.id,
                    position=i,
                    text=chunk,
                    embedding=vectors[i] if i < len(vectors) else None,
                )
            )
        await self.session.flush()
        return len(chunks)

    async def _retrieve_chunks(
        self, material: LearningMaterial, query: str, *, top_k: int | None = None
    ) -> list[str]:
        """Return the top-k most relevant chunk texts for a query.

        Deterministic: embeds the query with the same provider and ranks chunks
        by cosine similarity, breaking ties by chunk position. Falls back to the
        first chunks (and finally the raw text prefix) when no embeddings exist.
        """
        from sqlalchemy import select

        top_k = top_k or settings.material_rag_top_k
        stmt = (
            select(MaterialChunk)
            .where(MaterialChunk.material_id == material.id)
            .order_by(MaterialChunk.position)
        )
        chunks = list((await self.session.execute(stmt)).scalars().all())
        if not chunks:
            # No index yet: fall back to a plain prefix of the raw text.
            return [(material.extracted_text or "")[: settings.material_rag_max_chars]]

        try:
            (qvec,) = await get_ai_provider().embed([query or material.filename])
        except Exception:  # noqa: BLE001
            qvec = None
        if not qvec or all(c.embedding is None for c in chunks):
            return [c.text for c in chunks[:top_k]]

        scored: list[tuple[float, int, str]] = []
        for c in chunks:
            sim = cosine_similarity(qvec, c.embedding) if c.embedding else 0.0
            scored.append((sim, -c.position, c.text))
        scored.sort(reverse=True)
        return [t for _s, _p, t in scored[:top_k]]

    async def _grounded_text(self, material: LearningMaterial, query: str) -> str:
        chunks = await self._retrieve_chunks(material, query)
        return "\n\n".join(c for c in chunks if c)[: settings.material_rag_max_chars]


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

    async def presigned_download(
        self, material_id: uuid.UUID, user: User, *, ttl_seconds: int = 300
    ) -> str | None:
        """Return a presigned download URL (MinIO) or None for local storage.

        Authorization is enforced exactly like the streaming download, so a
        presigned URL is only ever handed to a permitted viewer.
        """
        material = await self.get_viewable(material_id, user)
        return storage.presigned_get_url(material.storage_key, expires_seconds=ttl_seconds)

    async def delete(self, material_id: uuid.UUID, user: User) -> None:
        """Delete a material (owner or admin) and its stored object.

        Refuses while the material still has AI draft questions awaiting review
        (409), so approving them after the source is gone can never orphan them.
        """
        from sqlalchemy import func, select

        material = await self.get(material_id)
        self._authorize(material, user)
        pending = (
            await self.session.execute(
                select(func.count())
                .select_from(Question)
                .where(
                    Question.material_id == material_id,
                    Question.review_status == "pending",
                )
            )
        ).scalar_one()
        if pending:
            raise ConflictError(
                "Materi masih punya draf soal yang menunggu tinjauan. "
                "Setujui atau tolak drafnya sebelum menghapus."
            )
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

    async def list_for_lesson(
        self, lesson_id: uuid.UUID, user: User, *, limit: int = 100, offset: int = 0
    ) -> list[LearningMaterial]:
        """Materials attached to a lesson, visible to its course's members.

        A student may list materials only for a lesson whose course they belong
        to; the owning teacher and admins see everything. A lesson with no
        course (or a non-member) is refused with 403.
        """
        from sqlalchemy import select

        from app.models.learning import Lesson

        lesson = await self.session.get(Lesson, lesson_id)
        if lesson is None:
            raise NotFoundError("Lesson not found")
        # Owner/admin of any material on this lesson may list it.
        if not user.has_role("admin"):
            is_member = lesson.course_id is not None and await self._is_course_member(
                lesson.course_id, user.id
            )
            owns_material = (
                await self.session.execute(
                    select(LearningMaterial.id)
                    .where(
                        LearningMaterial.lesson_id == lesson_id,
                        LearningMaterial.owner_id == user.id,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none() is not None
            if not is_member and not owns_material:
                raise ForbiddenError("You are not enrolled in this lesson's course")
        stmt = (
            select(LearningMaterial)
            .where(LearningMaterial.lesson_id == lesson_id)
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
        # Meter the AI request (1 ORT, or a free-tier slot). Insufficient ORT
        # raises 402 and rolls back the job in the same transaction.
        from app.services.ai_usage_service import AiUsageService

        await AiUsageService(self.session).charge_job(user=user, job_id=job.id)
        log.info("generation_enqueued", job_id=str(job.id))
        return job

    async def run_generation_job(self, job: GradingJob) -> list[Question]:
        """Execute a generation job and own its terminal status.

        Both the synchronous endpoint and the async worker call this, so the
        ``done``/``failed``/``queued`` transitions live in exactly one place
        instead of being duplicated in each caller.
        """
        from datetime import UTC, datetime

        job.status = "running"
        job.started_at = job.started_at or datetime.now(UTC)
        try:
            questions = await self.run_generation(job)
        except Exception as exc:  # noqa: BLE001 - record and re-raise
            job.error_code = "generation_error"
            job.error_message = str(exc)[:500]
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.finished_at = datetime.now(UTC)
                from app.services.ai_usage_service import AiUsageService

                await AiUsageService(self.session).refund_job(
                    user_id=job.owner_id, job_id=job.id
                )
            else:
                from datetime import timedelta

                job.status = "queued"
                job.available_at = datetime.now(UTC) + timedelta(
                    seconds=min(600, 2 ** max(job.attempts, 1))
                )
            await self.session.flush()
            raise
        job.status = "done"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_message = None
        await self.session.flush()
        return questions

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
        # Retrieve a broad, representative window (query = filename + opening)
        # via RAG, so a long document is summarised from relevant chunks.
        grounded = await self._grounded_text(material, (material.filename or "ringkasan"))
        return await provider.summarize(
            SummaryContext(text=grounded, language=language, max_words=max_words)
        )

    async def ask(self, material_id: uuid.UUID, user: User, *, question: str, language: str = "id"):
        """AI Q&A grounded on a material's text (owner, admin, or enrolled student)."""
        material = await self.get(material_id)
        await self._authorize_view(material, user)
        provider = get_ai_provider()
        grounded = await self._grounded_text(material, question)
        return await provider.answer(
            QAContext(text=grounded, question=question, language=language)
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
