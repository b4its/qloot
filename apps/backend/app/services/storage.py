"""Object storage abstraction: local filesystem or MinIO/S3."""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.logging import get_logger

if TYPE_CHECKING:
    from minio import Minio

log = get_logger("storage")


class Storage:
    """Small storage interface. Local by default; MinIO when configured."""

    def __init__(self) -> None:
        self.use_local = settings.use_local_storage
        self._client: Minio | None = None
        if not self.use_local:
            self._init_minio()

    def _init_minio(self) -> None:
        from minio import Minio

        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not self._client.bucket_exists(settings.minio_bucket):
            self._client.make_bucket(settings.minio_bucket)
        log.info("minio_initialised", bucket=settings.minio_bucket)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        if self.use_local:
            path = Path(settings.storage_local_dir) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return key
        assert self._client is not None
        self._client.put_object(
            settings.minio_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return key

    def get(self, key: str) -> bytes:
        if self.use_local:
            path = Path(settings.storage_local_dir) / key
            if not path.exists():
                raise ValidationError("Stored object not found")
            return path.read_bytes()
        assert self._client is not None
        resp = self._client.get_object(settings.minio_bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def delete(self, key: str) -> None:
        """Best-effort object removal; a missing object is not an error."""
        try:
            if self.use_local:
                path = Path(settings.storage_local_dir) / key
                path.unlink(missing_ok=True)
                return
            assert self._client is not None
            self._client.remove_object(settings.minio_bucket, key)
        except Exception as exc:  # noqa: BLE001 - cleanup must not fail the request
            log.warning("storage_delete_failed", key=key, error=str(exc))

    def presigned_get_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        """Return a time-limited presigned download URL, or None for local storage.

        Local storage has no HTTP origin to presign against, so callers fall back
        to streaming the object (see the download endpoint).
        """
        if self.use_local:
            return None
        assert self._client is not None
        from datetime import timedelta

        try:
            return self._client.presigned_get_object(
                settings.minio_bucket, key, expires=timedelta(seconds=expires_seconds)
            )
        except Exception as exc:  # noqa: BLE001 - fall back to a streaming download
            log.warning("presign_failed", key=key, error=str(exc))
            return None

    def ping(self) -> bool:
        """True when the backing store is reachable (used by readiness)."""
        try:
            if self.use_local:
                Path(settings.storage_local_dir).mkdir(parents=True, exist_ok=True)
                return True
            assert self._client is not None
            self._client.bucket_exists(settings.minio_bucket)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("storage_ping_failed", error=str(exc))
            return False


storage = Storage()


def scan_for_viruses(data: bytes) -> bool:
    """Antivirus policy hook (LEARN-07).

    A real deployment would call ClamAV/ICAP here. The default is a documented
    no-op that accepts the content; wire a scanner by overriding this function
    (or injecting one) without touching call sites.
    """
    # TODO(security): integrate ClamAV; return False to reject a document.
    return True


def build_key(owner_id: uuid.UUID, filename: str) -> str:
    """Build a hardned object key for an uploaded material.

    The key is forced to ``.pdf`` (the only accepted type) and the caller never
    controls the path beyond a random uuid, so a crafted filename cannot escape
    the materials prefix or smuggle a different extension.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext != ".pdf":
        ext = ".pdf"
    return f"materials/{owner_id}/{uuid.uuid4().hex}{ext}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff_pdf(data: bytes) -> bool:
    """Validate MIME by content, not by the client-provided header."""
    return data[:5] == b"%PDF-"


def sniff_image(data: bytes) -> str | None:
    """Validate an avatar upload by magic bytes; returns the sniffed MIME
    type or None if it isn't a recognised image (AUTH-04).
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None
