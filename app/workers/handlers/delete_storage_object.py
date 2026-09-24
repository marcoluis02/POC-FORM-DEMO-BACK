from typing import Any

from app.workers.task_context import TaskContext


async def delete_storage_object(payload: dict[str, Any], context: TaskContext) -> None:
    """Borra un archivo del storage (ej. una foto que el usuario quitó). Si falla, el worker reintenta."""
    await context.storage.delete(payload["key"])
