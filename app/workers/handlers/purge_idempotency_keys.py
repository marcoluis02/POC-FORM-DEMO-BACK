import logging
from typing import Any

from app.utils.time import utc_now
from app.workers.task_context import TaskContext

logger = logging.getLogger(__name__)


async def purge_expired_idempotency_keys(_: dict[str, Any], context: TaskContext) -> None:
    """Borra las claves de idempotencia vencidas por lotes; cada lote en su propia transacción corta."""
    batch_size = context.settings.idempotency_purge_batch_size
    total = 0
    while True:
        async with context.uow_factory() as uow:
            deleted = await uow.idempotency.delete_expired_batch(utc_now(), batch_size)
            await uow.commit()
        total += deleted
        if deleted < batch_size:
            break
    if total:
        logger.info("Claves de idempotencia vencidas borradas: %s", total)
