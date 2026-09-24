from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import IdempotencyKeyTakenError
from app.models.idempotency_key import IdempotencyKey
from app.repositories.base_repository import BaseRepository


class IdempotencyRepository(BaseRepository[IdempotencyKey]):
    model = IdempotencyKey

    async def add(self, entity: IdempotencyKey) -> IdempotencyKey:
        try:
            return await super().add(entity)
        except IntegrityError as exc:
            raise IdempotencyKeyTakenError() from exc

    async def get_active(self, key: str, scope: str, now: datetime) -> IdempotencyKey | None:
        stmt = select(IdempotencyKey).where(
            IdempotencyKey.idempotency_key == key,
            IdempotencyKey.scope == scope,
            IdempotencyKey.expires_at > now,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def delete_expired_key(self, key: str, scope: str, now: datetime) -> None:
        """Libera la clave si ya venció, para poder reutilizarla."""
        stmt = delete(IdempotencyKey).where(
            IdempotencyKey.idempotency_key == key,
            IdempotencyKey.scope == scope,
            IdempotencyKey.expires_at <= now,
        )
        await self._session.execute(stmt)

    async def delete_expired_batch(self, now: datetime, batch_size: int) -> int:
        """Borra claves vencidas por lotes para no bloquear la tabla. Regresa cuántas borró."""
        expired_ids = (
            select(IdempotencyKey.id)
            .where(IdempotencyKey.expires_at <= now)
            .limit(batch_size)
            .scalar_subquery()
        )
        result = await self._session.execute(delete(IdempotencyKey).where(IdempotencyKey.id.in_(expired_ids)))
        return result.rowcount or 0
