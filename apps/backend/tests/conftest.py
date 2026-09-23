"""Pytest configuration.

Tests require PostgreSQL because the schema uses JSONB and native UUID types.
A dedicated test database is created/dropped per session.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("BLOCKCHAIN_DRY_RUN", "true")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("USE_LOCAL_STORAGE", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")
# Tests exercise endpoints in tight loops; the rate limiter is a no-op for
# app_env=test (the dedicated rate-limit test re-enables it per-case).
os.environ.setdefault("APP_ENV", "test")

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://qloot:change-me@localhost:55433/qloot_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


async def provision_user(
    sess: AsyncSession,
    *,
    email: str,
    role: str = "student",
    password: str = "Password123!",
    full_name: str = "Test User",
    class_code: str | None = None,
    class_type: str | None = None,
):
    """Seed a user of any role straight through the auth service.

    Self-registration is student-only since the C01 hardening, so tests that
    need a teacher/admin account provision it here (the way an admin would via
    ``POST /admin/users``) instead of going through ``/auth/register``.
    """
    from app.services.auth_service import AuthService

    user, _token = await AuthService(sess).register(
        email=email,
        full_name=full_name,
        password=password,
        role=role,
        class_code=class_code,
        class_type=class_type,
        issue_session=False,
    )
    await sess.commit()
    return user


@pytest_asyncio.fixture
async def make_actor(engine):
    """Return an async helper that provisions a user and returns an authenticated
    client bound to that user's session cookie.

    Usage::

        teacher = await make_actor("t@ex.com", role="teacher")
        await teacher.client.post("/api/v1/courses", json={"title": "x"})
    """
    from dataclasses import dataclass

    sm = async_sessionmaker(engine, expire_on_commit=False)

    @dataclass
    class _Actor:
        client: AsyncClient
        user: object

    async def _make(email: str, role: str = "student", password: str = "Password123!"):
        async with sm() as s:
            await provision_user(s, email=email, role=role, password=password)

        transport = ASGITransport(app=app)

        async def _override_get_db():
            async with sm() as s:
                try:
                    yield s
                    if s.in_transaction():
                        await s.commit()
                except Exception:
                    if s.in_transaction():
                        await s.rollback()
                    raise

        app.dependency_overrides[get_db] = _override_get_db
        c = AsyncClient(transport=transport, base_url="http://test")
        login = await c.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.text
        actor = _Actor(client=c, user=login.json())
        return actor

    yield _make
    app.dependency_overrides.clear()



@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        yield s


@pytest_asyncio.fixture(autouse=True)
async def _seed_roles(engine):
    from sqlalchemy import select

    from app.models.identity import Role

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        for name, desc in [("student", "s"), ("teacher", "t"), ("admin", "a")]:
            existing = (await s.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
            if existing is None:
                s.add(Role(name=name, description=desc))
        await s.commit()
    yield


@pytest_asyncio.fixture
async def client(engine) -> AsyncIterator[AsyncClient]:
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with sm() as s:
            try:
                yield s
                if s.in_transaction():
                    await s.commit()
            except Exception:
                if s.in_transaction():
                    await s.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c._sm = sm  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
