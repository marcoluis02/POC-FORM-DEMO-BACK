import asyncio
import logging
import threading
from datetime import timedelta

from app.cloud.s3_storage import S3Storage
from app.core.config import Settings
from app.core.database import DATABASE_UNAVAILABLE_ERRORS, build_engine, build_session_factory
from app.core.unit_of_work import UnitOfWork
from app.models.worker_task import WorkerTask
from app.services.worker_task_service import enqueue_task
from app.utils.time import utc_now
from app.workers.task_context import TaskContext
from app.workers.task_registry import TASK_HANDLERS, recurring_dedupe_key, recurring_intervals

logger = logging.getLogger(__name__)

ERROR_MESSAGE_MAX_LENGTH = 2000
STOP_TIMEOUT_SECONDS = 10


class WorkerRunner:
    """Hilo aparte dentro del mismo servidor. Lee worker_tasks, procesa las pendientes y marca
    cada una como completed, o como error guardando el motivo en error_message.
    Tiene su propio event loop y su propio pool pequeño para no quitarle conexiones a la API."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="worker-tasks", daemon=True)
        self._recurring = recurring_intervals(settings)

    def start(self) -> None:
        self._thread.start()
        logger.info("Worker iniciado")

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=STOP_TIMEOUT_SECONDS)
        logger.info("Worker detenido")

    def _run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        engine = build_engine(self._settings, self._settings.worker_db_pool_size, max_overflow=0)
        session_factory = build_session_factory(engine)
        context = TaskContext(
            uow_factory=lambda: UnitOfWork(session_factory),
            settings=self._settings,
            storage=S3Storage(self._settings),
        )
        recurring_scheduled = False
        try:
            while not self._stop.is_set():
                try:
                    if not recurring_scheduled:
                        await self._schedule_recurring(context)
                        recurring_scheduled = True
                    claimed = await self._process_batch(context)
                except DATABASE_UNAVAILABLE_ERRORS as exc:
                    logger.warning("Worker sin base de datos: %s", type(exc).__name__)
                    claimed = 0
                except Exception:
                    logger.exception("Error inesperado en el worker")
                    claimed = 0
                # Si el lote vino lleno hay más trabajo: sigue sin esperar
                if claimed < self._settings.worker_batch_size:
                    await asyncio.to_thread(self._stop.wait, self._settings.worker_poll_interval_seconds)
        finally:
            await engine.dispose()

    async def _schedule_recurring(self, context: TaskContext) -> None:
        async with context.uow_factory() as uow:
            for task_type in self._recurring:
                await enqueue_task(uow, task_type, dedupe_key=recurring_dedupe_key(task_type))
            await uow.commit()

    async def _process_batch(self, context: TaskContext) -> int:
        now = utc_now()
        stale_before = now - timedelta(seconds=self._settings.worker_task_timeout_seconds)
        async with context.uow_factory() as uow:
            tasks = await uow.worker_tasks.claim_batch(self._settings.worker_batch_size, now, stale_before)
            await uow.commit()

        for task in tasks:
            await self._process_task(task, context)
        return len(tasks)

    async def _process_task(self, task: WorkerTask, context: TaskContext) -> None:
        handler = TASK_HANDLERS.get(task.task_type)
        try:
            if handler is None:
                raise LookupError(f"No hay handler para la tarea '{task.task_type}'.")
            await asyncio.wait_for(
                handler(task.payload, context), timeout=self._settings.worker_task_timeout_seconds
            )
        except Exception as exc:
            await self._mark_failed(task, exc, context)
            return

        async with context.uow_factory() as uow:
            await uow.worker_tasks.mark_completed(task.id, utc_now())
            await self._reschedule_if_recurring(uow, task)
            await uow.commit()

    async def _mark_failed(self, task: WorkerTask, exc: Exception, context: TaskContext) -> None:
        now = utc_now()
        can_retry = task.attempts < self._settings.worker_max_attempts
        retry_at = now + timedelta(seconds=self._settings.worker_retry_delay_seconds) if can_retry else None
        message = f"{type(exc).__name__}: {exc}"[:ERROR_MESSAGE_MAX_LENGTH]
        logger.warning("Tarea %s (%s) falló, intento %s: %s", task.id, task.task_type, task.attempts, message)

        async with context.uow_factory() as uow:
            await uow.worker_tasks.mark_failed(task.id, message, retry_at, now)
            if not can_retry:
                await self._reschedule_if_recurring(uow, task)
            await uow.commit()

    async def _reschedule_if_recurring(self, uow: UnitOfWork, task: WorkerTask) -> None:
        interval = self._recurring.get(task.task_type)
        if interval is not None:
            await enqueue_task(
                uow, task.task_type, task.payload, run_at=utc_now() + interval, dedupe_key=task.dedupe_key
            )
