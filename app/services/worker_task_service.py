import uuid
from datetime import datetime
from typing import Any

from app.domain.worker_task_type import WorkerTaskType
from app.interfaces.unit_of_work import UnitOfWorkInterface
from app.utils.time import utc_now


async def enqueue_task(
    uow: UnitOfWorkInterface,
    task_type: WorkerTaskType,
    payload: dict[str, Any] | None = None,
    *,
    run_at: datetime | None = None,
    dedupe_key: str | None = None,
) -> uuid.UUID | None:
    """Función única para mandarle trabajo al worker.

    Se guarda dentro de la misma transacción de quien la llama: si esa operación falla, la tarea
    tampoco se crea. run_at deja la tarea para más tarde. dedupe_key evita duplicar una tarea
    que ya está pendiente (en ese caso regresa None).

    Ejemplo:
        async with uow:
            await enqueue_task(uow, WorkerTaskType.X, {"id": str(algo.id)})
            await uow.commit()
    """
    return await uow.worker_tasks.enqueue(
        task_type=task_type,
        payload=payload or {},
        available_at=run_at or utc_now(),
        dedupe_key=dedupe_key,
    )
