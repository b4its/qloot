"""Certificate issuance + verification (simulated credentials)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", class_code=None, class_type=None):
    payload = {
        "email": email,
        "full_name": "Cert Student",
        "password": "Password123!",
        "role": role,
    }
    if class_code:
        payload["class_code"] = class_code
        payload["class_type"] = class_type
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


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
    assert v["recipient_name"] == "Cert Student"


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
