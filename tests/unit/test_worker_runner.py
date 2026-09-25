import uuid
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.domain.document_types import DocumentMimeType
from app.dto.form_definition import FormDefinitionInput
from app.factories.import_factory import build_import
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
def context(uow_factory, fake_storage, fake_extraction_provider):
    return TaskContext(
        uow_factory=uow_factory,
        settings=get_settings(),
        storage=fake_storage,
        extraction_provider=fake_extraction_provider,
    )


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


async def test_tarea_de_borrar_archivo_lo_quita_del_storage(runner, context, fake_db, fake_storage):
    fake_storage.objects["responses/r/foto.png"] = (b"x", "image/png")
    task = SimpleNamespace(
        id=uuid.uuid4(),
        task_type=WorkerTaskType.DELETE_STORAGE_OBJECT,
        payload={"key": "responses/r/foto.png"},
        attempts=1,
        dedupe_key=None,
    )

    await runner._process_task(task, context)

    assert fake_storage.objects == {}
    assert _actions(fake_db) == ["completed"]


async def test_tarea_sin_handler_queda_con_error(runner, context, fake_db):
    task = _task(attempts=get_settings().worker_max_attempts)
    task.task_type = "tarea_que_no_existe"

    await runner._process_task(task, context)

    assert _actions(fake_db) == ["failed"]
    assert "No hay handler" in fake_db.worker_tasks[0]["error_message"]


async def _seed_import(uow_factory, fake_storage):
    entity = build_import("worker-form.pdf", DocumentMimeType.PDF, 1)
    async with uow_factory() as uow:
        await uow.imports.add(entity)
        await uow.commit()
    fake_storage.objects[entity.original_file_key] = (b"%PDF-1.4 test", "application/pdf")
    return entity


async def test_extract_import_reintenta_falla_transitoria_y_luego_completa(
    runner, context, fake_db, fake_storage, fake_extraction_provider, uow_factory
):
    entity = await _seed_import(uow_factory, fake_storage)
    fake_extraction_provider.queue_error("ai_timeout", "timeout", retryable=True)

    first_attempt = SimpleNamespace(
        id=uuid.uuid4(),
        task_type=WorkerTaskType.EXTRACT_IMPORT,
        payload={"import_id": str(entity.id)},
        attempts=1,
        dedupe_key=f"extract_import:{entity.id}",
    )
    await runner._process_task(first_attempt, context)

    assert fake_db.worker_tasks[-1]["action"] == "failed"
    assert fake_db.worker_tasks[-1]["retry_at"] is not None
    assert fake_db.imports[entity.id].status == "processing"

    fake_extraction_provider.queue_result(
        FormDefinitionInput.model_validate(
            {
                "schema_version": 1,
                "title": "Formulario worker",
                "sections": [
                    {
                        "id": None,
                        "title": "General",
                        "position": 1,
                        "fields": [
                            {
                                "id": None,
                                "type": "short_text",
                                "label": "Nombre",
                                "required": False,
                                "position": 1,
                                "allow_evidence": False,
                                "unit": None,
                                "options": None,
                            }
                        ],
                    }
                ],
            }
        )
    )
    second_attempt = SimpleNamespace(
        id=first_attempt.id,
        task_type=first_attempt.task_type,
        payload=first_attempt.payload,
        attempts=2,
        dedupe_key=first_attempt.dedupe_key,
    )
    await runner._process_task(second_attempt, context)

    assert fake_db.worker_tasks[-1]["action"] == "completed"
    assert fake_db.imports[entity.id].status == "requires_review"


async def test_extract_import_agota_retries_y_cierra_import_en_failed(
    runner, context, fake_db, fake_storage, fake_extraction_provider, uow_factory
):
    entity = await _seed_import(uow_factory, fake_storage)
    fake_extraction_provider.queue_error("ai_timeout", "timeout final", retryable=True)

    task = SimpleNamespace(
        id=uuid.uuid4(),
        task_type=WorkerTaskType.EXTRACT_IMPORT,
        payload={"import_id": str(entity.id)},
        attempts=get_settings().worker_max_attempts,
        dedupe_key=f"extract_import:{entity.id}",
    )
    await runner._process_task(task, context)

    assert fake_db.worker_tasks[-1]["action"] == "failed"
    assert fake_db.worker_tasks[-1]["retry_at"] is None
    assert fake_db.imports[entity.id].status == "failed"
    assert fake_db.imports[entity.id].error_code == "ai_timeout"
