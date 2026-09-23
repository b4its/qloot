"""Shared test helpers.

Self-registration is student-only since the C01 hardening, so teacher/admin
accounts are provisioned the way an admin would (``POST /admin/users``) —
directly through the auth service — and then authenticated via ``/auth/login``.
This keeps the many existing tests that need a privileged actor working without
weakening the public registration contract.
"""

from __future__ import annotations

from typing import Any


async def register_actor(
    client: Any,
    email: str,
    role: str = "student",
    *,
    password: str = "Password123!",
    full_name: str = "Test User",
    class_code: str | None = None,
    class_type: str | None = None,
) -> dict:
    """Register (or provision) a user and return the ``UserOut`` payload.

    ``role="student"`` goes through the real ``/auth/register`` endpoint.
    Privileged roles are seeded out-of-band and then logged in.
    """
    if role == "student":
        payload: dict[str, Any] = {
            "email": email,
            "full_name": full_name,
            "password": password,
            "role": "student",
        }
        if class_code:
            payload["class_code"] = class_code
        if class_type:
            payload["class_type"] = class_type
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    # Privileged account: seed directly, then log in to get a session cookie.
    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        from app.services.auth_service import AuthService

        await AuthService(s).register(
            email=email,
            full_name=full_name,
            password=password,
            role=role,
            class_code=class_code,
            class_type=class_type,
            issue_session=False,
        )
        await s.commit()

    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200, login.text
    return login.json()
