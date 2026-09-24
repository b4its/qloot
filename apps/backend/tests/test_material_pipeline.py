"""Material extraction-quality signalling with OCR fallback (C39)."""

from __future__ import annotations

import pytest

from tests.helpers import register_actor
from tests.pdf_util import make_pdf

pytestmark = pytest.mark.integration


async def _upload(client, pdf: bytes) -> dict:
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("scan.pdf", pdf, "application/pdf")},
        data={"title": "Materi"},
    )
    assert up.status_code == 201, up.text
    return up.json()


async def test_text_pdf_marked_ok(client):
    await register_actor(client, "ex_ok@ex.com", "teacher")
    body = "Fotosintesis adalah proses tumbuhan mengubah cahaya matahari menjadi energi."
    m = await _upload(client, make_pdf(body))
    assert m["extraction_status"] == "ok"


async def test_textless_pdf_marked_empty(client):
    """A scanned/text-less PDF is flagged at upload, not left to fail late."""
    await register_actor(client, "ex_empty@ex.com", "teacher")
    m = await _upload(client, make_pdf(""))
    assert m["extraction_status"] == "empty"


async def test_ocr_disabled_by_default(client):
    from app.core.config import settings

    assert settings.material_ocr_enabled is False
