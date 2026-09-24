"""Certificate (credential) endpoints — simulated, verifiable credentials."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import AdminUser, CurrentUser, DbSession, LimitParam, OffsetParam, OptionalUser
from app.db.session import transaction
from app.schemas.certificate import CertificateOut, CertificateVerifyOut, RevokeRequest
from app.services.certificate_service import CertificateService

router = APIRouter(prefix="/certificates", tags=["certificates"])


def _mask_name(name: str | None) -> str:
    """Privacy-preserving display of a recipient name for the *public* verify.

    Keeps the first name and the initial(s) of the rest ("Budi Santoso" →
    "Budi S.") so a holder can recognise their own credential without the public
    endpoint disclosing a full legal name to anyone with the link.
    """
    if not name:
        return "—"
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    initials = " ".join(f"{p[0]}." for p in parts[1:] if p)
    return f"{parts[0]} {initials}".strip()


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
        # Masked: the public verify must not leak a full legal name.
        recipient_name=_mask_name(cert.recipient_name),
        issued_by=cert.issued_by,
        issued_at=cert.issued_at,
        verification_hash=cert.verification_hash,
        anchor_status=cert.anchor_status,
        anchor_tx_hash=cert.anchor_tx_hash,
    )


@router.post("/sync", response_model=list[CertificateOut])
async def sync(user: CurrentUser, db: DbSession):
    """Re-check all completed courses and issue any missing certificates."""
    async with transaction(db):
        certs = await CertificateService(db).sync_for_user(user)
    return [CertificateService.out(c) for c in certs]


@router.get("/{credential_id}/render")
async def render_certificate(credential_id: str, request: Request, db: DbSession):
    """Render a printable certificate document (HTML) with a verification mark.

    Public (a certificate holder may print it), but a revoked certificate is
    refused. The document embeds the verify URL and QTC anchoring status.
    """
    from fastapi.responses import HTMLResponse

    from app.core.config import settings
    from app.core.errors import NotFoundError
    from app.services.certificate_service import CertificateService

    base_url = settings.app_url or str(request.base_url)
    html = await CertificateService(db).render_document(credential_id, base_url=base_url)
    if html is None:
        raise NotFoundError("Certificate not found")
    return HTMLResponse(html)


@router.post("/{credential_id}/anchor", response_model=CertificateOut)
async def anchor(credential_id: str, user: CurrentUser, db: DbSession):
    """Anchor the certificate's hash on-chain (QTC). Owner or admin only."""
    from app.core.errors import NotFoundError

    async with transaction(db):
        cert = await CertificateService(db).anchor(user, credential_id)
    if cert is None:
        raise NotFoundError("Certificate not found")
    return CertificateService.out(cert)


@router.post("/{credential_id}/revoke", response_model=CertificateOut)
async def revoke(credential_id: str, payload: RevokeRequest, admin: AdminUser, db: DbSession):
    """Revoke a certificate (admin only). Idempotent."""
    from app.core.errors import NotFoundError

    async with transaction(db):
        cert = await CertificateService(db).revoke(credential_id, reason=payload.reason)
    if cert is None:
        raise NotFoundError("Certificate not found")
    return CertificateService.out(cert)
