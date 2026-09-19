"""Async database engine, session factory and transaction helpers.

The transaction helper fixes the SayGenFix bug where a `defer commit` ran even
on error: here the transaction commits ONLY if the block completes without an
exception, otherwise it rolls back.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency.

    Commits once at the end of a successful request; rolls back on any error.
    Endpoints should NOT commit manually — wrapping writes in `transaction()`
    simply joins this request-level transaction.
    """
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Logical transaction scope.

    If a transaction is already open (e.g. from a dependency query), we simply
    participate in it — the outer unit of work (request or session_scope) is
    responsible for commit/rollback. Otherwise we open one and commit/rollback
    it ourselves.
    """
    if session.in_transaction():
        # Join the existing unit of work.
        yield session
        return
    async with session.begin():
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Standalone session + transaction for workers and background tasks."""
    sm = get_sessionmaker()
    async with sm() as session, session.begin():
        yield session
