from datetime import datetime
from typing import Protocol

from app.models.idempotency_key import IdempotencyKey


class IdempotencyRepositoryInterface(Protocol):
    async def add(self, entity: IdempotencyKey) -> IdempotencyKey: ...

    async def get_active(self, key: str, scope: str, now: datetime) -> IdempotencyKey | None: ...

    async def delete_expired_key(self, key: str, scope: str, now: datetime) -> None: ...

    async def delete_expired_batch(self, now: datetime, batch_size: int) -> int: ...
