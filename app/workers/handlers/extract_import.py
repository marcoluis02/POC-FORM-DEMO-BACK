import uuid
from typing import Any

from app.services.extraction_service import ExtractionService
from app.workers.task_context import TaskContext


def _import_id(payload: dict[str, Any]) -> uuid.UUID:
    raw_import_id = payload.get("import_id")
    try:
        return uuid.UUID(str(raw_import_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("La tarea extract_import no trae un import_id válido.") from exc


async def extract_import(payload: dict[str, Any], context: TaskContext) -> None:
    service = ExtractionService(context.uow_factory, context.storage, context.extraction_provider)
    await service.process(_import_id(payload))


async def finalize_extract_import_failure(
    payload: dict[str, Any],
    context: TaskContext,
    error: Exception,
) -> None:
    """Sincroniza el estado de form_imports cuando el worker agotó sus retries."""
    service = ExtractionService(context.uow_factory, context.storage, context.extraction_provider)
    await service.finalize_retry_exhausted(_import_id(payload), error)
