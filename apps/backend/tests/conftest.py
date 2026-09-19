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

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://qloot:change-me@localhost:55433/qloot_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL

from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


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
