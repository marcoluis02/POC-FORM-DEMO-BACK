import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.domain.worker_task_status import WorkerTaskStatus
from app.models.worker_task import WorkerTask
from app.repositories.base_repository import BaseRepository

ACTIVE_DEDUPE_WHERE = text("status IN ('pending', 'processing') AND dedupe_key IS NOT NULL")


class WorkerTasksRepository(BaseRepository[WorkerTask]):
    model = WorkerTask

    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        available_at: datetime,
        dedupe_key: str | None,
    ) -> uuid.UUID | None:
        """Crea la tarea en pending. Si ya hay una activa con el mismo dedupe_key no hace nada y regresa None."""
        stmt = (
            insert(WorkerTask)
            .values(
                id=uuid.uuid4(),
                task_type=task_type,
                payload=payload,
                status=WorkerTaskStatus.PENDING,
                dedupe_key=dedupe_key,
                attempts=0,
                available_at=available_at,
            )
            .on_conflict_do_nothing(index_elements=["dedupe_key"], index_where=ACTIVE_DEDUPE_WHERE)
            .returning(WorkerTask.id)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def claim_batch(self, batch_size: int, now: datetime, stale_before: datetime) -> list[WorkerTask]:
        """Toma tareas listas y las marca en proceso. También recupera las que se quedaron trabadas.
        SKIP LOCKED evita que dos workers tomen la misma tarea."""
        ready = and_(WorkerTask.status == WorkerTaskStatus.PENDING, WorkerTask.available_at <= now)
        stuck = and_(WorkerTask.status == WorkerTaskStatus.PROCESSING, WorkerTask.started_at < stale_before)
        claimable_ids = (
            select(WorkerTask.id)
            .where(or_(ready, stuck))
            .order_by(WorkerTask.available_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(WorkerTask)
            .where(WorkerTask.id.in_(claimable_ids))
            .values(
                status=WorkerTaskStatus.PROCESSING,
                attempts=WorkerTask.attempts + 1,
                started_at=now,
                updated_at=now,
            )
            .returning(WorkerTask)
        )
        result = await self._session.scalars(stmt, execution_options={"synchronize_session": False})
        return list(result)

    async def mark_completed(self, task_id: uuid.UUID, now: datetime) -> None:
        stmt = (
            update(WorkerTask)
            .where(WorkerTask.id == task_id)
            .values(status=WorkerTaskStatus.COMPLETED, error_message=None, finished_at=now, updated_at=now)
        )
        await self._session.execute(stmt, execution_options={"synchronize_session": False})

    async def mark_failed(
        self, task_id: uuid.UUID, error_message: str, retry_at: datetime | None, now: datetime
    ) -> None:
        """Si hay retry_at la tarea vuelve a pending para reintentarse; si no, queda en error."""
        stmt = (
            update(WorkerTask)
            .where(WorkerTask.id == task_id)
            .values(
                status=WorkerTaskStatus.PENDING if retry_at else WorkerTaskStatus.ERROR,
                error_message=error_message,
                available_at=retry_at or WorkerTask.available_at,
                finished_at=None if retry_at else now,
                updated_at=now,
            )
        )
        await self._session.execute(stmt, execution_options={"synchronize_session": False})
