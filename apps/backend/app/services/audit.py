"""Audit log helper: every write carries the request_id from context.

AUTH-05: AuditLog.request_id existed as a column but no application code
path ever populated it (only the seeder set it as fabricated demo data).
Every audit write should go through record() so request correlation is
never forgotten again, and to allow adding auth-event auditing.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import AuditLog


def current_request_id() -> str | None:
    """The request_id bound by RequestContextMiddleware for this request, if
    any (background/worker contexts have none — that's fine, the column is
    nullable).
    """
    ctx = structlog.contextvars.get_contextvars()
    value = ctx.get("request_id")
    return str(value) if value else None


def record(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    data: dict | None = None,
) -> AuditLog:
    """Add an AuditLog row (caller is responsible for flush/commit via the
    surrounding transaction), with request_id populated from context.
    """
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        data=data,
        request_id=current_request_id(),
    )
    session.add(row)
    return row
