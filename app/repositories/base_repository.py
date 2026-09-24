import uuid
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD común. Solo hace flush: el commit lo decide la Unit of Work."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def update(self, entity: ModelT) -> ModelT:
        """Manda a la BD los cambios hechos a una entidad ya cargada (y llena updated_at)."""
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self._session.delete(entity)
        await self._session.flush()
