import uuid
from datetime import datetime
from typing import Any, Protocol

from app.models.worker_task import WorkerTask


class WorkerTasksRepositoryInterface(Protocol):
    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        available_at: datetime,
        dedupe_key: str | None,
    ) -> uuid.UUID | None: ...

    async def claim_batch(self, batch_size: int, now: datetime, stale_before: datetime) -> list[WorkerTask]: ...

    async def mark_completed(self, task_id: uuid.UUID, now: datetime) -> None: ...

    async def mark_failed(
        self, task_id: uuid.UUID, error_message: str, retry_at: datetime | None, now: datetime
    ) -> None: ...
