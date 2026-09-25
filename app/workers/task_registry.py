from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.domain.worker_task_type import WorkerTaskType
from app.workers.handlers.delete_storage_object import delete_storage_object
from app.workers.handlers.extract_import import extract_import, finalize_extract_import_failure
from app.workers.handlers.purge_idempotency_keys import purge_expired_idempotency_keys
from app.workers.task_context import TaskContext

TaskHandler = Callable[[dict[str, Any], TaskContext], Awaitable[None]]
TaskFailureHandler = Callable[[dict[str, Any], TaskContext, Exception], Awaitable[None]]

TASK_HANDLERS: dict[str, TaskHandler] = {
    WorkerTaskType.EXTRACT_IMPORT: extract_import,
    WorkerTaskType.PURGE_EXPIRED_IDEMPOTENCY_KEYS: purge_expired_idempotency_keys,
    WorkerTaskType.DELETE_STORAGE_OBJECT: delete_storage_object,
}

# Solo tareas cuyo dominio necesita cerrar estado propio al agotarse los retries.
TASK_FAILURE_HANDLERS: dict[str, TaskFailureHandler] = {
    WorkerTaskType.EXTRACT_IMPORT: finalize_extract_import_failure,
}


def recurring_intervals(settings: Settings) -> dict[str, timedelta]:
    return {
        WorkerTaskType.PURGE_EXPIRED_IDEMPOTENCY_KEYS: timedelta(
            minutes=settings.idempotency_purge_interval_minutes
        ),
    }


def recurring_dedupe_key(task_type: str) -> str:
    return f"recurring:{task_type}"
