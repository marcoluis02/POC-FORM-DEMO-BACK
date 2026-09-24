from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.domain.worker_task_type import WorkerTaskType
from app.workers.handlers.delete_storage_object import delete_storage_object
from app.workers.handlers.purge_idempotency_keys import purge_expired_idempotency_keys
from app.workers.task_context import TaskContext

TaskHandler = Callable[[dict[str, Any], TaskContext], Awaitable[None]]

# Qué función procesa cada tipo de tarea. Para una tarea nueva: agregar el tipo y su handler aquí.
TASK_HANDLERS: dict[str, TaskHandler] = {
    WorkerTaskType.PURGE_EXPIRED_IDEMPOTENCY_KEYS: purge_expired_idempotency_keys,
    WorkerTaskType.DELETE_STORAGE_OBJECT: delete_storage_object,
}


def recurring_intervals(settings: Settings) -> dict[str, timedelta]:
    """Tareas que se repiten solas: al terminar (bien o con error) se vuelven a programar."""
    return {
        WorkerTaskType.PURGE_EXPIRED_IDEMPOTENCY_KEYS: timedelta(
            minutes=settings.idempotency_purge_interval_minutes
        ),
    }


def recurring_dedupe_key(task_type: str) -> str:
    return f"recurring:{task_type}"
