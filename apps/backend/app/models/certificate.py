"""Certificate (credential) model — simulated, verifiable learning credentials.

A certificate is issued when a student completes every published lesson of a
course. It carries a unique, human-readable credential id and a verification
hash so it can be shared/linked as a (simulated) digital credential.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        # One certificate per (user, course).
        UniqueConstraint("user_id", "course_id", name="uq_certificates_user_course"),
        Index("ix_certificates_user_issued", "user_id", "issued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    # Human-readable credential id, e.g. QLT-MAT1A-0142-7F9A2C.
    credential_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Short verification token used to build the /verify link (opaque).
    verification_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Snapshot of what was earned (title shown on the certificate).
    course_title: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_by: Mapped[str] = mapped_column(String(255), default="QLoot Academy", nullable=False)
    # Global edition number within the certificate programme (1..N).
    edition_number: Mapped[int] = mapped_column(nullable=False)
    edition_total: Mapped[int] = mapped_column(default=5000, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(255))
