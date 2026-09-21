"""Certificate service (simulated credentials).

Certificates are issued deterministically when a student has completed every
published lesson of a course. They carry a unique credential id and a
verification hash so the credential can be looked up / verified.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.certificate import Certificate
from app.models.identity import User
from app.models.learning import Course, Lesson, LessonProgress

log = get_logger("certificates")

EDITION_TOTAL = 5000


def _prefix_from_title(title: str) -> str:
    """Build a short uppercase code from a course title, e.g. 'Matematika 1A' -> 'MAT1A'."""
    words = [w for w in title.upper().replace("-", " ").split() if w.isalnum()]
    if not words:
        return "QLT"
    code = "".join(w[0] for w in words[:3] if w) or "QLT"
    # Keep it recognisable: first word (truncated) + initials of the rest.
    head = words[0][:3]
    rest = "".join(w[0] for w in words[1:3])
    return (head + rest)[:6] or code


def _verification_hash(credential_id: str) -> str:
    return hashlib.sha256(f"qloot-cert|{credential_id}".encode()).hexdigest()[:32]


class CertificateService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _course_is_complete(self, user_id: uuid.UUID, course_id: uuid.UUID) -> bool:
        lesson_ids = (
            select(Lesson.id)
            .where(Lesson.course_id == course_id, Lesson.is_published.is_(True))
            .scalar_subquery()
        )
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(Lesson)
                .where(Lesson.course_id == course_id, Lesson.is_published.is_(True))
            )
        ).scalar_one()
        if not total:
            return False
        done = (
            await self.session.execute(
                select(func.count())
                .select_from(LessonProgress)
                .where(
                    LessonProgress.user_id == user_id,
                    LessonProgress.lesson_id.in_(lesson_ids),
                    LessonProgress.completed.is_(True),
                )
            )
        ).scalar_one()
        return int(done) >= int(total)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Certificate]:
        stmt = (
            select(Certificate)
            .where(Certificate.user_id == user_id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_credential(self, credential_id: str) -> Certificate | None:
        stmt = select(Certificate).where(Certificate.credential_id == credential_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def issue_for_course(self, user: User, course_id: uuid.UUID) -> Certificate | None:
        """Issue (idempotently) a certificate if the course is fully completed."""
        existing = (
            await self.session.execute(
                select(Certificate).where(
                    Certificate.user_id == user.id, Certificate.course_id == course_id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        if not await self._course_is_complete(user.id, course_id):
            return None

        course = await self.session.get(Course, course_id)
        if course is None:
            return None

        # Serialise edition-number assignment with a transaction-scoped advisory
        # lock: concurrent issuances for *different* users would otherwise read
        # the same count and mint the same edition number.
        await self.session.execute(select(func.pg_advisory_xact_lock(0xC0DE_C3_01)))
        edition = (
            int(
                (
                    await self.session.execute(select(func.count()).select_from(Certificate))
                ).scalar_one()
            )
            + 1
        )
        prefix = _prefix_from_title(course.title)
        credential_id = f"QLT-{prefix}-{edition:04d}-{uuid.uuid4().hex[:6].upper()}"
        cert = Certificate(
            user_id=user.id,
            course_id=course_id,
            credential_id=credential_id,
            verification_hash=_verification_hash(credential_id),
            course_title=course.title,
            recipient_name=user.full_name,
            issued_by="QLoot Academy",
            edition_number=edition,
            edition_total=EDITION_TOTAL,
            issued_at=datetime.now(UTC),
        )
        self.session.add(cert)
        await self.session.flush()
        log.info("certificate_issued", user=str(user.id), course=str(course_id))
        return cert

    async def sync_for_user(self, user: User) -> list[Certificate]:
        """Issue certificates for all of the user's fully-completed courses."""
        # Courses the student can see and has progress in.
        course_ids = list(
            (
                await self.session.execute(
                    select(LessonProgress.course_id)
                    .where(LessonProgress.user_id == user.id)
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for cid in course_ids:
            await self.issue_for_course(user, cid)
        return await self.list_for_user(user.id)

    @staticmethod
    def out(cert: Certificate) -> dict:
        return {
            "id": cert.id,
            "credential_id": cert.credential_id,
            "verification_hash": cert.verification_hash,
            "course_id": cert.course_id,
            "course_title": cert.course_title,
            "recipient_name": cert.recipient_name,
            "issued_by": cert.issued_by,
            "edition_number": cert.edition_number,
            "edition_total": cert.edition_total,
            "issued_at": cert.issued_at,
            "revoked_at": cert.revoked_at,
        }
