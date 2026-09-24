import uuid
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.domain.worker_task_type import WorkerTaskType
from app.workers import worker_runner as runner_module
from app.workers.task_context import TaskContext
from app.workers.task_registry import recurring_dedupe_key
from app.workers.worker_runner import WorkerRunner

PURGE = WorkerTaskType.PURGE_EXPIRED_IDEMPOTENCY_KEYS


def _task(attempts: int = 1):
    return SimpleNamespace(
        id=uuid.uuid4(), task_type=PURGE, payload={}, attempts=attempts, dedupe_key=recurring_dedupe_key(PURGE)
    )


@pytest.fixture
def context(uow_factory):
    return TaskContext(uow_factory=uow_factory, settings=get_settings())


@pytest.fixture
def runner():
    return WorkerRunner(get_settings())


def _actions(fake_db):
    return [item["action"] for item in fake_db.worker_tasks]


async def test_tarea_exitosa_se_marca_completa_y_se_reprograma(runner, context, fake_db):
    await runner._process_task(_task(), context)

    assert _actions(fake_db) == ["completed", "enqueue"]
    assert fake_db.worker_tasks[1]["dedupe_key"] == recurring_dedupe_key(PURGE)


async def test_tarea_fallida_vuelve_a_pending_si_quedan_intentos(runner, context, fake_db, monkeypatch):
    async def broken(_, __):
        raise RuntimeError("fallo de prueba")

    monkeypatch.setitem(runner_module.TASK_HANDLERS, PURGE, broken)

    await runner._process_task(_task(attempts=1), context)

    assert _actions(fake_db) == ["failed"]
    assert fake_db.worker_tasks[0]["retry_at"] is not None
    assert "fallo de prueba" in fake_db.worker_tasks[0]["error_message"]


async def test_ultimo_intento_fallido_queda_en_error_y_se_reprograma(runner, context, fake_db, monkeypatch):
    async def broken(_, __):
        raise RuntimeError("fallo de prueba")

    monkeypatch.setitem(runner_module.TASK_HANDLERS, PURGE, broken)

    await runner._process_task(_task(attempts=get_settings().worker_max_attempts), context)

    assert _actions(fake_db) == ["failed", "enqueue"]
    assert fake_db.worker_tasks[0]["retry_at"] is None


async def test_tarea_sin_handler_queda_con_error(runner, context, fake_db):
    task = _task(attempts=get_settings().worker_max_attempts)
    task.task_type = "tarea_que_no_existe"

    await runner._process_task(task, context)

    assert _actions(fake_db) == ["failed"]
    assert "No hay handler" in fake_db.worker_tasks[0]["error_message"]
