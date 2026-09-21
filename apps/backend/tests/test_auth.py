"""Auth + authorization tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", password="Password123!"):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": password, "role": role},
    )
    return resp


async def test_register_login_me_logout(client):
    resp = await _register(client, "alice@example.com")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert "student" in body["roles"]
    assert body["chain_user_ref"].startswith("0x")

    # Session cookie set.
    assert client.cookies.get("qloot_session")

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    me2 = await client.get("/api/v1/auth/me")
    assert me2.status_code == 401


async def test_duplicate_email_rejected(client):
    assert (await _register(client, "bob@example.com")).status_code == 201
    dup = await _register(client, "bob@example.com")
    assert dup.status_code == 409


async def test_login_wrong_password(client):
    await _register(client, "carol@example.com")
    await client.post("/api/v1/auth/logout")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "carol@example.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


async def test_protected_route_requires_auth(client):
    resp = await client.get("/api/v1/courses")
    assert resp.status_code == 401


async def test_login_lockout(client, engine):
    """After too many failures the account is temporarily locked."""
    from app.core.config import settings

    email = "locky@example.com"
    await _register(client, email)
    await client.post("/api/v1/auth/logout")

    for _ in range(settings.login_max_attempts):
        await client.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!"}
    )
    assert resp.status_code == 401
    assert "lock" in resp.json()["error"]["message"].lower()


async def test_student_cannot_create_course(client):
    await _register(client, "stud@example.com", role="student")
    resp = await client.post("/api/v1/courses", json={"title": "Hack Course"})
    assert resp.status_code == 403


async def test_student_cannot_create_lesson(client):
    await _register(client, "lesson_t@example.com", role="teacher")
    course = await client.post(
        "/api/v1/courses",
        json={"title": "Kelas Materi", "class_code": "1A", "class_type": "IPA"},
    )
    course_id = course.json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "lesson_s@example.com", role="student")
    resp = await client.post(f"/api/v1/courses/{course_id}/lessons", json={"title": "Langgar"})
    assert resp.status_code in (401, 403)


async def test_teacher_can_create_course(client):
    await _register(client, "teach@example.com", role="teacher")
    resp = await client.post(
        "/api/v1/courses",
        json={
            "title": "Matematika 1A",
            "subject": "Matematika",
            "class_code": "1A",
            "class_type": "IPA",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Matematika 1A"
    assert body["class_code"] == "1A"


async def test_sessions_listing_and_revoke(client):
    await _register(client, "sessions@example.com")
    sessions = await client.get("/api/v1/auth/sessions")
    assert sessions.status_code == 200
    items = sessions.json()
    assert len(items) >= 1
    sid = items[0]["id"]
    revoke = await client.delete(f"/api/v1/auth/sessions/{sid}")
    assert revoke.status_code == 200


async def test_password_reset_full_flow(client):
    """Forgot-password returns a dev token that can reset the password."""
    await _register(client, "reset_me@example.com", password="OldPassword1!")
    await client.post("/api/v1/auth/logout")

    forgot = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "reset_me@example.com"}
    )
    assert forgot.status_code == 200, forgot.text
    token = forgot.json().get("reset_token")
    assert token  # non-production returns the token for the simulated flow

    reset = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "NewPassword2!"}
    )
    assert reset.status_code == 200, reset.text

    # Old password no longer works; the new one does.
    old = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset_me@example.com", "password": "OldPassword1!"},
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset_me@example.com", "password": "NewPassword2!"},
    )
    assert new.status_code == 200


async def test_password_reset_rejects_bad_token(client):
    await _register(client, "reset_bad@example.com")
    await client.post("/api/v1/auth/logout")
    bad = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "Whatever1!"},
    )
    assert bad.status_code == 422


async def test_forgot_password_does_not_leak_unknown_email(client):
    resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.example"}
    )
    assert resp.status_code == 200
    # Unknown email yields no token but the same generic message.
    assert resp.json()["reset_token"] is None
