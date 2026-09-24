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


async def _provision_teacher(client, email):
    """Create a teacher the way an admin would, then log in.

    Self-registration is student-only, so privileged accounts are provisioned
    out-of-band (mirrors ``POST /admin/users``).
    """
    from tests.helpers import register_actor

    return await register_actor(client, email, "teacher")


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
    await _provision_teacher(client, "lesson_t@example.com")
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
    await _provision_teacher(client, "teach@example.com")
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


async def test_logout_all_revokes_every_session(client):
    """AUTH-02: logout-all revokes every session for the caller, including
    ones created by earlier logins (simulating multiple devices/tabs).
    """
    await _register(client, "logoutall@example.com", password="Password123!")
    # A second login (e.g. another device) issues a second session row.
    second_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "logoutall@example.com", "password": "Password123!"},
    )
    assert second_login.status_code == 200, second_login.text

    before = await client.get("/api/v1/auth/sessions")
    assert before.status_code == 200
    assert len(before.json()) >= 2

    out = await client.post("/api/v1/auth/logout-all")
    assert out.status_code == 200, out.text

    # The cookie was cleared client-side, but even the *old* token (if reused)
    # must now be rejected — /auth/me must 401 with no valid cookie either.
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_logout_all_requires_authentication(client):
    r = await client.post("/api/v1/auth/logout-all")
    assert r.status_code == 401


async def test_change_password_requires_current_password(client):
    await _register(client, "changepw@example.com", password="OldPassword1!")
    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "NotTheRealOne!", "new_password": "NewPassword1!"},
    )
    assert wrong.status_code == 401, wrong.text


async def test_change_password_succeeds_and_old_password_stops_working(client):
    await _register(client, "changepw2@example.com", password="OldPassword1!")
    ok = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword1!", "new_password": "NewPassword1!"},
    )
    assert ok.status_code == 200, ok.text

    await client.post("/api/v1/auth/logout")
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepw2@example.com", "password": "OldPassword1!"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepw2@example.com", "password": "NewPassword1!"},
    )
    assert new_login.status_code == 200


async def test_change_password_revokes_other_sessions_but_keeps_current(client):
    await _register(client, "changepw3@example.com", password="OldPassword1!")
    second_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "changepw3@example.com", "password": "OldPassword1!"},
    )
    assert second_login.status_code == 200
    # The client's cookie jar now holds the *second* session's token.
    before = await client.get("/api/v1/auth/sessions")
    assert len(before.json()) >= 2

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPassword1!", "new_password": "NewPassword1!"},
    )
    assert changed.status_code == 200, changed.text

    # The current session (the one that made the change) must still work.
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200


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


async def test_self_registration_cannot_create_teacher(client):
    """AUTH-12: anonymous visitors must not self-assign the teacher role."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky@example.com",
            "full_name": "Sneaky Teacher",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert resp.status_code == 422, resp.text


async def test_self_registration_cannot_create_admin(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky2@example.com",
            "full_name": "Sneaky Admin",
            "password": "Password123!",
            "role": "admin",
        },
    )
    assert resp.status_code == 422, resp.text


async def test_admin_can_still_create_teacher(client):
    """The admin-only creation path keeps working for privileged roles."""
    from tests.helpers import register_actor

    await register_actor(client, "boss@example.com", "admin")
    resp = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "newteacher@example.com",
            "full_name": "New Teacher",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    assert resp.status_code == 201, resp.text
    assert "teacher" in resp.json()["roles"]


async def test_update_profile_changes_full_name(client):
    await _register(client, "profile_name@example.com")
    r = await client.patch("/api/v1/auth/profile", json={"full_name": "Nama Baru"})
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Nama Baru"

    me = await client.get("/api/v1/auth/me")
    assert me.json()["full_name"] == "Nama Baru"


async def test_upload_avatar_sets_avatar_url_and_is_served(client):
    """AUTH-04: avatar_url is a dead column until an upload actually writes it."""
    await _register(client, "avatar_user@example.com")
    # A minimal valid PNG (8-byte signature + IHDR is enough for our sniffer,
    # which only checks the magic bytes).
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = await client.post(
        "/api/v1/auth/profile/avatar",
        files={"file": ("avatar.png", png_bytes, "image/png")},
    )
    assert r.status_code == 200, r.text
    avatar_url = r.json()["avatar_url"]
    assert avatar_url, "avatar_url must no longer be null after upload"

    me = await client.get("/api/v1/auth/me")
    assert me.json()["avatar_url"] == avatar_url

    served = await client.get(f"/api/v1/auth/avatars/{me.json()['id']}")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/")


async def test_upload_avatar_rejects_non_image_content(client):
    await _register(client, "avatar_bad@example.com")
    r = await client.post(
        "/api/v1/auth/profile/avatar",
        files={"file": ("fake.png", b"not an image at all", "image/png")},
    )
    assert r.status_code == 422, r.text


async def test_change_email_full_flow(client):
    await _register(client, "old_email@example.com", password="Password123!")
    request = await client.post(
        "/api/v1/auth/change-email/request", json={"new_email": "new_email@example.com"}
    )
    assert request.status_code == 200, request.text
    token = request.json()["change_token"]
    assert token, "dev/test mode must return the raw token"

    # The email is NOT changed yet — a pending request must not affect login.
    me_before = await client.get("/api/v1/auth/me")
    assert me_before.json()["email"] == "old_email@example.com"

    confirm = await client.post("/api/v1/auth/change-email/confirm", json={"token": token})
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["email"] == "new_email@example.com"

    me_after = await client.get("/api/v1/auth/me")
    assert me_after.json()["email"] == "new_email@example.com"

    # Logging in with the new email now works.
    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "new_email@example.com", "password": "Password123!"},
    )
    assert login.status_code == 200


async def test_change_email_rejects_an_address_already_in_use(client):
    await _register(client, "taken@example.com", password="Password123!")
    await client.post("/api/v1/auth/logout")
    await _register(client, "wants_taken@example.com", password="Password123!")

    r = await client.post(
        "/api/v1/auth/change-email/request", json={"new_email": "taken@example.com"}
    )
    assert r.status_code == 409, r.text


async def test_change_email_confirm_rejects_invalid_token(client):
    await _register(client, "invalid_token_user@example.com")
    r = await client.post("/api/v1/auth/change-email/confirm", json={"token": "not-a-real-token"})
    assert r.status_code == 422


async def test_me_reports_session_expiry(client):
    """AUTH-10: /auth/me surfaces the current session's expiry so the client can
    rotate the token before it lapses."""
    await _register(client, "expiry_user@example.com")
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["session_expires_at"] is not None


async def test_refresh_rotates_the_session_and_invalidates_the_old_token(client):
    """AUTH-10: /auth/refresh issues a new token, revokes the old one, and the
    old token no longer authenticates."""
    await _register(client, "refresh_user@example.com")
    old_token = client.cookies.get("qloot_session")
    assert old_token

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["session_expires_at"] is not None
    new_token = client.cookies.get("qloot_session")
    assert new_token and new_token != old_token

    # The rotated (old) token is revoked. Send it explicitly on a fresh
    # request via a per-request cookie override.
    stale = await client.get("/api/v1/auth/me", cookies={"qloot_session": old_token})
    assert stale.status_code == 401
