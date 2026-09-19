"""Generic async repository helpers."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def get_by(self, **filters: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(
        self, stmt: Select | None = None, *, limit: int = 100, offset: int = 0
    ) -> list[ModelT]:
        stmt = stmt if stmt is not None else select(self.model)
        stmt = stmt.limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self, stmt: Select | None = None) -> int:
        base = stmt if stmt is not None else select(self.model)
        sub = base.subquery()
        return int((await self.session.execute(select(func.count()).select_from(sub))).scalar_one())

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
