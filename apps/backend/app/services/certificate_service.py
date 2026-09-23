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
from sqlalchemy.exc import IntegrityError
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

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Certificate]:
        stmt = (
            select(Certificate)
            .where(Certificate.user_id == user_id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc())
            .limit(limit)
            .offset(offset)
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
        # Re-check under the lock: a concurrent request for the *same* (user,
        # course) may have inserted between the check above and the lock.
        existing = (
            await self.session.execute(
                select(Certificate).where(
                    Certificate.user_id == user.id, Certificate.course_id == course_id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
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
        try:
            # SAVEPOINT so a duplicate (user, course) from a racing request only
            # unwinds this insert instead of failing the whole request with a
            # 500. Mirrors BadgeService.award.
            async with self.session.begin_nested():
                self.session.add(cert)
                await self.session.flush()
        except IntegrityError:
            return (
                await self.session.execute(
                    select(Certificate).where(
                        Certificate.user_id == user.id, Certificate.course_id == course_id
                    )
                )
            ).scalar_one_or_none()
        log.info("certificate_issued", user=str(user.id), course=str(course_id))
        # Course completion pays OPT once per (user, course) — README economy.
        from app.core.config import settings
        from app.services.keys import course_completion_key
        from app.services.reward_engine import RewardEngine

        await RewardEngine(self.session).allocate_event_reward(
            user=user,
            amount=settings.reward_course_completion,
            reward_type="course_completion",
            rkey=course_completion_key(course_id, user.id),
            description=f"Course completed: {course.title}",
        )
        await self._notify_issued(user, course.title)
        return cert

    async def _notify_issued(self, user: User, course_title: str) -> None:
        """Tell the learner they earned a certificate (best-effort)."""
        from app.services.social_service import NotificationService

        try:
            await NotificationService(self.session).notify(
                user_id=user.id,
                kind="badge",
                title="Sertifikat diterbitkan! 🎓",
                body=f"Selamat! Kamu menyelesaikan {course_title} dan mendapat sertifikat digital.",
            )
        except Exception as exc:  # noqa: BLE001 - never block issuance on notify
            log.warning("certificate_notify_failed", error=str(exc))

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

    async def revoke(self, credential_id: str, *, reason: str | None = None) -> Certificate | None:
        """Revoke a certificate by credential id (idempotent).

        The verify path already reports ``valid=False`` for a revoked credential
        and the listing filters them out; this is the missing mutation side.
        Returns the certificate (or None if the id is unknown).
        """
        cert = await self.get_by_credential(credential_id)
        if cert is None:
            return None
        if cert.revoked_at is not None:
            return cert
        cert.revoked_at = datetime.now(UTC)
        if reason:
            cert.revoked_reason = reason
        await self.session.flush()
        log.info("certificate_revoked", credential_id=credential_id)
        await self._notify_revoked(cert)
        return cert

    async def anchor(self, user: User, credential_id: str) -> Certificate | None:
        """Anchor a certificate's verification hash on-chain (QTC-funded).

        Debits one QTC from the owner, enqueues a ``certificate_anchor`` outbox
        item (the worker writes the hash on QTC) and marks the cert
        ``anchoring``. Idempotent: an already-anchored/anchoring cert is
        returned unchanged, so re-clicking never double-spends or double-writes.
        """
        from app.models.wallet import TransactionOutbox
        from app.services.keys import certificate_anchor_key, tx_idempotency_key
        from app.services.reward_engine import RewardEngine

        cert = await self.get_by_credential(credential_id)
        if cert is None:
            return None
        if cert.user_id != user.id and not user.has_role("admin"):
            from app.core.errors import ForbiddenError

            raise ForbiddenError("You do not own this certificate")
        if cert.revoked_at is not None:
            from app.core.errors import ConflictError

            raise ConflictError("A revoked certificate cannot be anchored")
        if cert.anchor_status in ("anchoring", "submitted", "anchored"):
            return cert

        engine = RewardEngine(self.session)
        # 1 QTC per anchoring (the documented QTC sink).
        await engine.debit_asset(user_id=cert.user_id, asset="QTC", amount=1)
        cert.anchor_status = "anchoring"
        await self.session.flush()

        anchor_key = certificate_anchor_key(cert.id)
        self.session.add(
            TransactionOutbox(
                topic="certificate_anchor",
                idempotency_key=tx_idempotency_key("anchor", str(cert.id)),
                payload={
                    "certificate_id": str(cert.id),
                    "anchor_key": anchor_key,
                    "document_hash": "0x" + cert.verification_hash,
                    "user_id": str(cert.user_id),
                    "qtc_cost": 1,
                },
                status="pending",
            )
        )
        await self.session.flush()
        log.info("certificate_anchor_queued", credential_id=credential_id)
        return cert

    async def _notify_revoked(self, cert: Certificate) -> None:
        from app.services.social_service import NotificationService

        try:
            await NotificationService(self.session).notify(
                user_id=cert.user_id,
                kind="system",
                title="Sertifikat dicabut",
                body=f"Sertifikat untuk {cert.course_title} telah dicabut.",
            )
        except Exception as exc:  # noqa: BLE001 - never block revoke on notify
            log.warning("certificate_revoke_notify_failed", error=str(exc))

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
            "revoked_reason": cert.revoked_reason,
            "anchor_status": cert.anchor_status,
            "anchor_tx_hash": cert.anchor_tx_hash,
            "anchored_at": cert.anchored_at,
        }
