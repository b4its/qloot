"""Certificate (credential) endpoints — simulated, verifiable credentials."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, LimitParam, OffsetParam, OptionalUser
from app.db.session import transaction
from app.schemas.certificate import CertificateOut, CertificateVerifyOut
from app.services.certificate_service import CertificateService

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("", response_model=list[CertificateOut])
async def my_certificates(
    user: CurrentUser, db: DbSession, limit: LimitParam = 100, offset: OffsetParam = 0
):
    """List the caller's certificates, issuing any newly-earned ones first."""
    async with transaction(db):
        # Ensure newly-earned certificates exist, then page the listing.
        await CertificateService(db).sync_for_user(user)
        certs = await CertificateService(db).list_for_user(user.id, limit=limit, offset=offset)
    return [CertificateService.out(c) for c in certs]


@router.get("/verify/{credential_id}", response_model=CertificateVerifyOut)
async def verify(credential_id: str, user: OptionalUser, db: DbSession):
    """Public verification of a credential id (no auth required)."""
    cert = await CertificateService(db).get_by_credential(credential_id)
    if cert is None:
        return CertificateVerifyOut(valid=False, credential_id=credential_id)
    return CertificateVerifyOut(
        valid=cert.revoked_at is None,
        credential_id=cert.credential_id,
        course_title=cert.course_title,
        recipient_name=cert.recipient_name,
        issued_by=cert.issued_by,
        issued_at=cert.issued_at,
        verification_hash=cert.verification_hash,
    )


@router.post("/sync", response_model=list[CertificateOut])
async def sync(user: CurrentUser, db: DbSession):
    """Re-check all completed courses and issue any missing certificates."""
    async with transaction(db):
        certs = await CertificateService(db).sync_for_user(user)
    return [CertificateService.out(c) for c in certs]
