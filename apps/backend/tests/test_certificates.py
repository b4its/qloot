"""Certificate issuance + verification (simulated credentials)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", class_code=None, class_type=None):
    from tests.helpers import register_actor

    return await register_actor(
        client,
        email,
        role,
        full_name="Cert Student",
        class_code=class_code,
        class_type=class_type,
    )


async def test_certificate_issued_on_course_completion_and_verifiable(client):
    # Teacher creates a class-1A course with two lessons.
    await _register(client, "cert_teacher@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={
            "title": "Sertifikat 1A",
            "subject": "Fisika",
            "class_code": "1A",
            "class_type": "IPA",
            "is_published": True,
        },
    )
    assert course.status_code == 201, course.text
    course_id = course.json()["id"]

    lesson_ids = []
    for i in range(2):
        lesson = await client.post(
            f"/api/v1/courses/{course_id}/lessons",
            json={"title": f"Pertemuan {i + 1}", "content_md": "# Materi", "position": i},
        )
        assert lesson.status_code == 201, lesson.text
        lesson_ids.append(lesson.json()["id"])

    await client.post("/api/v1/auth/logout")

    # Student in class 1A completes both lessons.
    await _register(client, "cert_student@ex.com", "student", "1A", "IPA")

    # No certificate before completion.
    empty = await client.get("/api/v1/certificates")
    assert empty.status_code == 200
    assert empty.json() == []

    for lid in lesson_ids:
        r = await client.post(
            f"/api/v1/lessons/{lid}/progress",
            json={"progress_percent": 100, "completed": True},
        )
        assert r.status_code == 200, r.text

    certs = await client.get("/api/v1/certificates")
    assert certs.status_code == 200
    body = certs.json()
    assert len(body) == 1
    cert = body[0]
    assert cert["course_id"] == course_id
    assert cert["credential_id"].startswith("QLT-")
    assert cert["verification_hash"]

    # Public verification works and reports valid.
    verify = await client.get(f"/api/v1/certificates/verify/{cert['credential_id']}")
    assert verify.status_code == 200
    v = verify.json()
    assert v["valid"] is True
    assert v["course_title"] == "Sertifikat 1A"
    # Public verify masks the recipient's surname (privacy): "Cert Student"
    # becomes "Cert S." so a shared link can't harvest a full legal name.
    assert v["recipient_name"] == "Cert S."
    assert "Student" not in v["recipient_name"]


async def test_certificate_not_issued_until_all_lessons_done(client):
    await _register(client, "cert_t2@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={
            "title": "Dua Materi 2A",
            "class_code": "2A",
            "class_type": "IPA",
            "is_published": True,
        },
    )
    course_id = course.json()["id"]
    lids = []
    for i in range(2):
        lesson = await client.post(
            f"/api/v1/courses/{course_id}/lessons",
            json={"title": f"M{i}", "position": i},
        )
        lids.append(lesson.json()["id"])
    await client.post("/api/v1/auth/logout")

    await _register(client, "cert_s2@ex.com", "student", "2A", "IPA")
    await client.post(
        f"/api/v1/lessons/{lids[0]}/progress", json={"progress_percent": 100, "completed": True}
    )
    certs = await client.get("/api/v1/certificates")
    assert certs.json() == []


async def test_verification_of_unknown_credential_is_invalid(client):
    r = await client.get("/api/v1/certificates/verify/QLT-DOES-NOT-EXIST")
    assert r.status_code == 200
    assert r.json()["valid"] is False


async def _issue_cert(client, engine, *, code="1A", tag="anchor"):
    """Create a course+lesson, complete it as a student, return the certificate."""
    await _register(client, f"anc_t_{tag}@ex.com", "teacher")
    course = await client.post(
        "/api/v1/courses",
        json={
            "title": f"Anchor {code} {tag}",
            "class_code": code,
            "class_type": "IPA",
            "is_published": True,
        },
    )
    course_id = course.json()["id"]
    lesson = await client.post(
        f"/api/v1/courses/{course_id}/lessons", json={"title": "M1", "position": 0}
    )
    lid = lesson.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, f"anc_s_{tag}@ex.com", "student", code, "IPA")
    me = (await client.get("/api/v1/auth/me")).json()["id"]
    await client.post(
        f"/api/v1/lessons/{lid}/progress",
        json={"progress_percent": 100, "completed": True},
    )
    certs = (await client.get("/api/v1/certificates")).json()
    return certs[0], me


async def _credit_qtc(engine, user_id, amount: int):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.reward_engine import RewardEngine

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await RewardEngine(s).credit_asset(user_id=user_id, asset="QTC", amount=amount)
        await s.commit()


async def test_certificate_anchoring_requires_and_spends_qtc(client, engine):
    cert, me = await _issue_cert(client, engine, tag="need")
    cid = cert["credential_id"]

    # No QTC -> 402 (insufficient QTC balance).
    blocked = await client.post(f"/api/v1/certificates/{cid}/anchor")
    assert blocked.status_code == 409, blocked.text

    await _credit_qtc(engine, me, 1)
    ok = await client.post(f"/api/v1/certificates/{cid}/anchor")
    assert ok.status_code == 200, ok.text
    assert ok.json()["anchor_status"] == "anchoring"

    # QTC was debited.
    assets = (await client.get("/api/v1/wallet/assets")).json()["assets"]
    assert next(a["balance"] for a in assets if a["asset"] == "QTC") == 0


async def test_certificate_anchor_end_to_end_confirms(client, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.blockchain.worker_logic import process_outbox_item, refresh_confirmations
    from app.models.wallet import TransactionOutbox

    cert, me = await _issue_cert(client, engine, tag="e2e")
    cid = cert["credential_id"]
    await _credit_qtc(engine, me, 1)
    await client.post(f"/api/v1/certificates/{cid}/anchor")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        item = (
            await s.execute(
                select(TransactionOutbox).where(
                    TransactionOutbox.topic == "certificate_anchor",
                    TransactionOutbox.payload["certificate_id"].astext == cert["id"],
                )
            )
        ).scalars().first()
        assert item is not None
        await process_outbox_item(s, item.id)
        await refresh_confirmations(s)
        await s.commit()

    # Verify now reports the anchored status + tx hash.
    v = (await client.get(f"/api/v1/certificates/verify/{cid}")).json()
    assert v["anchor_status"] == "anchored"
    assert v["anchor_tx_hash"]

    # Re-anchoring is idempotent (no second outbox row, no extra QTC debit).
    await client.post(f"/api/v1/certificates/{cid}/anchor")
    async with sm() as s:
        rows = (
            await s.execute(
                select(TransactionOutbox).where(
                    TransactionOutbox.topic == "certificate_anchor",
                    TransactionOutbox.payload["certificate_id"].astext == cert["id"],
                )
            )
        ).scalars().all()
    assert len(rows) == 1
