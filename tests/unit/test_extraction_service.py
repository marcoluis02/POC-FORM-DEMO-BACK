from decimal import Decimal

import pytest

from app.domain.document_types import DocumentMimeType
from app.domain.import_status import ImportStatus
from app.dto.form_definition import FormDefinitionInput
from app.factories.import_factory import build_import
from app.interfaces.extraction_provider import ExtractionProviderError, ExtractionWarning
from app.services.extraction_service import ExtractionService


VALID_AI_DEFINITION = {
    "schema_version": 1,
    "title": "Inspección",
    "sections": [
        {
            "id": None,
            "title": "General",
            "position": 2,
            "fields": [
                {
                    "id": None,
                    "type": "short_text",
                    "label": "Nombre",
                    "required": True,
                    "position": 3,
                    "allow_evidence": False,
                    "unit": None,
                    "options": None,
                },
                {
                    "id": None,
                    "type": "yes_no_na",
                    "label": "¿Funciona?",
                    "required": False,
                    "position": 1,
                    "allow_evidence": True,
                    "unit": None,
                    "options": None,
                },
            ],
        }
    ],
}


async def _seed_import(uow_factory, fake_storage):
    entity = build_import("formulario.pdf", DocumentMimeType.PDF, 1)
    async with uow_factory() as uow:
        await uow.imports.add(entity)
        await uow.commit()
    fake_storage.objects[entity.original_file_key] = (b"%PDF-1.4 test", "application/pdf")
    return entity


async def test_extraccion_exitosa_normaliza_persiste_metricas_y_warnings(
    uow_factory, fake_db, fake_storage, fake_extraction_provider
):
    entity = await _seed_import(uow_factory, fake_storage)
    fake_extraction_provider.queue_result(
        FormDefinitionInput.model_validate(VALID_AI_DEFINITION),
        warnings=[ExtractionWarning(code="uncertain_text", message="Revisar una etiqueta")],
        estimated_cost=Decimal("0.001234"),
    )
    service = ExtractionService(uow_factory, fake_storage, fake_extraction_provider)

    await service.process(entity.id)

    stored = fake_db.imports[entity.id]
    assert stored.status == ImportStatus.REQUIRES_REVIEW
    assert stored.draft_json["sections"][0]["id"] == "s_001"
    assert [f["id"] for f in stored.draft_json["sections"][0]["fields"]] == ["f_001", "f_002"]
    assert [f["position"] for f in stored.draft_json["sections"][0]["fields"]] == [1, 2]
    assert stored.detected_fields_count == 2
    assert stored.estimated_cost == Decimal("0.001234")
    assert stored.corrections_count == 0
    assert stored.warnings[0]["code"] == "uncertain_text"
    assert stored.error_code is None


async def test_documento_sin_formulario_termina_failed_sin_draft(
    uow_factory, fake_db, fake_storage, fake_extraction_provider
):
    entity = await _seed_import(uow_factory, fake_storage)
    fake_extraction_provider.queue_result(
        None,
        warnings=[ExtractionWarning(code="no_form", message="No se detectaron campos")],
        estimated_cost=Decimal("0.000100"),
    )
    service = ExtractionService(uow_factory, fake_storage, fake_extraction_provider)

    await service.process(entity.id)

    stored = fake_db.imports[entity.id]
    assert stored.status == ImportStatus.FAILED
    assert stored.draft_json is None
    assert stored.error_code == "document_unreadable"
    assert stored.detected_fields_count == 0
    assert stored.estimated_cost == Decimal("0.000100")


async def test_error_permanente_del_provider_termina_failed_sin_retry(
    uow_factory, fake_db, fake_storage, fake_extraction_provider
):
    entity = await _seed_import(uow_factory, fake_storage)
    fake_extraction_provider.queue_error("ai_provider_error", "Credencial inválida", retryable=False)
    service = ExtractionService(uow_factory, fake_storage, fake_extraction_provider)

    await service.process(entity.id)

    stored = fake_db.imports[entity.id]
    assert stored.status == ImportStatus.FAILED
    assert stored.error_code == "ai_provider_error"
    assert stored.error_message == "Credencial inválida"


async def test_error_transitorio_se_propaga_al_worker_y_no_cierra_import(
    uow_factory, fake_db, fake_storage, fake_extraction_provider
):
    entity = await _seed_import(uow_factory, fake_storage)
    fake_extraction_provider.queue_error("ai_timeout", "Timeout", retryable=True)
    service = ExtractionService(uow_factory, fake_storage, fake_extraction_provider)

    with pytest.raises(ExtractionProviderError) as error:
        await service.process(entity.id)

    assert error.value.retryable is True
    stored = fake_db.imports[entity.id]
    assert stored.status == ImportStatus.PROCESSING
    assert stored.error_code is None
    assert stored.processing_started_at is not None
    assert stored.processing_finished_at is None


async def test_al_agotar_retry_el_import_queda_failed(
    uow_factory, fake_db, fake_storage, fake_extraction_provider
):
    entity = await _seed_import(uow_factory, fake_storage)
    service = ExtractionService(uow_factory, fake_storage, fake_extraction_provider)
    error = ExtractionProviderError("ai_timeout", "Timeout final", retryable=True)

    # Simula que un intento ya lo dejó processing.
    fake_extraction_provider.queue_error("ai_timeout", "Timeout", retryable=True)
    with pytest.raises(ExtractionProviderError):
        await service.process(entity.id)

    await service.finalize_retry_exhausted(entity.id, error)

    stored = fake_db.imports[entity.id]
    assert stored.status == ImportStatus.FAILED
    assert stored.error_code == "ai_timeout"
    assert stored.error_message == "Timeout final"
    assert stored.processing_finished_at is not None
