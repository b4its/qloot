"""Certificate (credential) schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CertificateOut(BaseModel):
    id: uuid.UUID
    credential_id: str
    verification_hash: str
    course_id: uuid.UUID
    course_title: str
    recipient_name: str
    issued_by: str
    edition_number: int
    edition_total: int
    issued_at: datetime
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    anchor_status: str = "unanchored"
    anchor_tx_hash: str | None = None
    anchored_at: datetime | None = None


class RevokeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class CertificateVerifyOut(BaseModel):
    valid: bool
    credential_id: str
    course_title: str | None = None
    recipient_name: str | None = None
    issued_by: str | None = None
    issued_at: datetime | None = None
    verification_hash: str | None = None
    anchor_status: str = "unanchored"
    anchor_tx_hash: str | None = None
