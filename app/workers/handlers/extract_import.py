import uuid
from typing import Any

from app.services.extraction_service import ExtractionService
from app.workers.task_context import TaskContext


async def extract_import(payload: dict[str, Any], context: TaskContext) -> None:
    raw_import_id = payload.get("import_id")
    try:
        import_id = uuid.UUID(str(raw_import_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("La tarea extract_import no trae un import_id válido.") from exc

    service = ExtractionService(context.uow_factory, context.storage, context.extraction_provider)
    await service.process(import_id)
