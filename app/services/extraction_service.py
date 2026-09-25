import logging
import uuid
from datetime import datetime
from decimal import Decimal

from app.domain.document_types import DocumentMimeType
from app.domain.import_status import ImportStatus
from app.dto.form_definition import FormDefinition
from app.interfaces.extraction_provider import (
    ExtractionInput,
    ExtractionProvider,
    ExtractionProviderError,
    ExtractionWarning,
)
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.unit_of_work import UnitOfWorkFactory
from app.services.definition_normalizer import normalize_definition
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

UNREADABLE_MESSAGE = "No fue posible extraer un formulario útil de este documento. Puedes revisarlo manualmente."
GENERIC_EXTRACTION_MESSAGE = "No pudimos procesar el documento con IA. Puedes intentar de nuevo o capturarlo manualmente."


class ExtractionService:
    """Orquesta storage -> proveedor IA -> validación -> persistencia del borrador.

    No crea plantillas. El resultado siempre queda en requires_review para que una persona
    lo revise y confirme explícitamente.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        storage: StorageProvider,
        provider: ExtractionProvider,
    ):
        self._uow_factory = uow_factory
        self._storage = storage
        self._provider = provider

    @staticmethod
    def _elapsed_ms(started_at: datetime, finished_at: datetime) -> int:
        return max(0, int((finished_at - started_at).total_seconds() * 1000))

    async def _begin(self, import_id: uuid.UUID) -> tuple[str, str, DocumentMimeType, datetime] | None:
        started_at = utc_now()
        async with self._uow_factory() as uow:
            entity = await uow.imports.get_for_update(import_id)
            if entity is None:
                # La tarea puede quedar huérfana si el registro se elimina fuera de este flujo.
                return None
            if entity.status == ImportStatus.REQUIRES_REVIEW:
                return None

            entity.status = ImportStatus.PROCESSING
            entity.processing_started_at = started_at
            entity.processing_finished_at = None
            entity.processing_ms = None
            entity.error_code = None
            entity.error_message = None
            entity.warnings = []
            entity.draft_json = None
            entity.detected_fields_count = None
            entity.estimated_cost = None
            entity.corrections_count = None
            await uow.imports.update(entity)
            await uow.commit()
            return entity.original_file_key, entity.original_filename, DocumentMimeType(entity.mime_type), started_at

    async def _finish_success(
        self,
        import_id: uuid.UUID,
        definition: FormDefinition,
        warnings: list[ExtractionWarning],
        estimated_cost: Decimal | None,
        started_at: datetime,
    ) -> None:
        finished_at = utc_now()
        detected_fields = sum(len(section.fields) for section in definition.sections)
        async with self._uow_factory() as uow:
            entity = await uow.imports.get_for_update(import_id)
            if entity is None or entity.status == ImportStatus.REQUIRES_REVIEW:
                return
            entity.status = ImportStatus.REQUIRES_REVIEW
            entity.draft_json = definition.model_dump(mode="json")
            entity.warnings = [warning.as_dict() for warning in warnings]
            entity.processing_finished_at = finished_at
            entity.processing_ms = self._elapsed_ms(started_at, finished_at)
            entity.estimated_cost = estimated_cost
            entity.detected_fields_count = detected_fields
            entity.corrections_count = 0
            entity.error_code = None
            entity.error_message = None
            await uow.imports.update(entity)
            await uow.commit()

    async def _finish_failed(
        self,
        import_id: uuid.UUID,
        code: str,
        message: str,
        started_at: datetime,
        warnings: list[ExtractionWarning] | None = None,
        estimated_cost: Decimal | None = None,
        detected_fields_count: int | None = None,
    ) -> None:
        finished_at = utc_now()
        async with self._uow_factory() as uow:
            entity = await uow.imports.get_for_update(import_id)
            if entity is None or entity.status == ImportStatus.REQUIRES_REVIEW:
                return
            entity.status = ImportStatus.FAILED
            entity.draft_json = None
            entity.warnings = [warning.as_dict() for warning in warnings or []]
            entity.processing_finished_at = finished_at
            entity.processing_ms = self._elapsed_ms(started_at, finished_at)
            entity.estimated_cost = estimated_cost
            entity.detected_fields_count = detected_fields_count
            entity.corrections_count = None
            entity.error_code = code
            entity.error_message = message
            await uow.imports.update(entity)
            await uow.commit()

    async def process(self, import_id: uuid.UUID) -> None:
        prepared = await self._begin(import_id)
        if prepared is None:
            return
        file_key, filename, mime_type, started_at = prepared

        try:
            content = await self._storage.get(file_key)
            result = await self._provider.extract(
                ExtractionInput(filename=filename, mime_type=mime_type, content=content)
            )
            if result.definition is None:
                await self._finish_failed(
                    import_id,
                    "document_unreadable",
                    UNREADABLE_MESSAGE,
                    started_at,
                    warnings=result.warnings,
                    estimated_cost=result.estimated_cost,
                    detected_fields_count=0,
                )
                return

            # La IA nunca es fuente de verdad. Aunque use Structured Outputs, vuelve a pasar
            # por el contrato del dominio y por la normalización de ids/posiciones del backend.
            definition = normalize_definition(result.definition)
            await self._finish_success(
                import_id,
                definition,
                result.warnings,
                result.estimated_cost,
                started_at,
            )
        except ExtractionProviderError as exc:
            await self._finish_failed(import_id, exc.code, exc.public_message, started_at)
        except Exception as exc:
            # No registrar el documento ni la respuesta del proveedor en logs.
            logger.warning("Extracción inesperada falló para import %s: %s", import_id, type(exc).__name__)
            await self._finish_failed(import_id, "extraction_failed", GENERIC_EXTRACTION_MESSAGE, started_at)
