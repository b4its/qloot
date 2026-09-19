"""Object storage abstraction: local filesystem or MinIO/S3."""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.logging import get_logger

log = get_logger("storage")


class Storage:
    """Small storage interface. Local by default; MinIO when configured."""

    def __init__(self) -> None:
        self.use_local = settings.use_local_storage
        self._client = None
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

    def put(self, key: str, data: bytes, content_type: str) -> str:
        if self.use_local:
            path = Path(settings.storage_local_dir) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return key
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
        resp = self._client.get_object(settings.minio_bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()


storage = Storage()


def build_key(owner_id: uuid.UUID, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"materials/{owner_id}/{uuid.uuid4().hex}{ext}"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff_pdf(data: bytes) -> bool:
    """Validate MIME by content, not by the client-provided header."""
    return data[:5] == b"%PDF-"
