import uuid

from app.core.exceptions import ErrorDetail, NotFoundError, ValidationError
from app.dto.form_definition import FormDefinition, FormDefinitionInput
from app.dto.templates import TemplateOut, TemplatePageOut, TemplateVersionOut
from app.factories.template_factory import (
    build_new_template,
    build_version,
    to_template_out,
    to_template_summary_out,
    to_version_out,
)
from app.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkInterface
from app.services.definition_diff import count_definition_corrections
from app.services.definition_normalizer import normalize_definition
from app.services.idempotency_service import IdempotencyService
from app.services.import_service import IMPORT_NOT_FOUND
from app.utils.cursor import decode_cursor, encode_cursor

TEMPLATE_NOT_FOUND = "No encontramos esta plantilla."
INVALID_CURSOR = "El enlace de la página no es válido. Vuelve a cargar el listado."


class TemplateService:
    def __init__(self, uow_factory: UnitOfWorkFactory, idempotency: IdempotencyService):
        self._uow_factory = uow_factory
        self._idempotency = idempotency

    @staticmethod
    async def _get_source_import(uow: UnitOfWorkInterface, source_import_id: uuid.UUID | None):
        if source_import_id is None:
            return None
        source_import = await uow.imports.get_for_update(source_import_id)
        if source_import is None:
            raise ValidationError(
                IMPORT_NOT_FOUND,
                code="source_import_not_found",
                details=[ErrorDetail("not_found", IMPORT_NOT_FOUND, field_id="source_import_id")],
            )
        return source_import

    @staticmethod
    async def _record_corrections(uow: UnitOfWorkInterface, source_import, definition: FormDefinition) -> None:
        if source_import is None or source_import.draft_json is None:
            return
        try:
            original = FormDefinition.model_validate(source_import.draft_json)
        except Exception:
            # La métrica no debe impedir crear una plantilla válida si un registro histórico está dañado.
            return
        source_import.corrections_count = count_definition_corrections(original, definition)
        await uow.imports.update(source_import)

    @staticmethod
    def _request_payload(data: FormDefinitionInput, source_import_id: uuid.UUID | None) -> dict:
        return {"definition": data.model_dump(mode="json"), "source_import_id": source_import_id}

    async def create_template(
        self,
        data: FormDefinitionInput,
        idempotency_key: str | None,
        source_import_id: uuid.UUID | None = None,
    ) -> TemplateOut:
        """Crea la plantilla y su versión 1 en una sola transacción."""

        async def operation(uow: UnitOfWorkInterface) -> TemplateOut:
            source_import = await self._get_source_import(uow, source_import_id)
            definition = normalize_definition(data)
            template, version = build_new_template(definition, source_import_id)
            await uow.templates.add(template)
            await uow.templates.add_version(version)
            await self._record_corrections(uow, source_import, definition)
            return to_template_out(template, version)

        return await self._idempotency.execute(
            key=idempotency_key,
            scope="templates.create",
            request_payload=self._request_payload(data, source_import_id),
            operation=operation,
            response_model=TemplateOut,
        )

    async def create_version(
        self,
        template_id: uuid.UUID,
        data: FormDefinitionInput,
        idempotency_key: str | None,
        source_import_id: uuid.UUID | None = None,
    ) -> TemplateOut:
        """Crea la versión n+1. Las versiones anteriores nunca se modifican.
        Sin source_import_id la nueva versión conserva el documento original de la anterior."""

        async def operation(uow: UnitOfWorkInterface) -> TemplateOut:
            template = await uow.templates.get_for_update(template_id)
            if template is None:
                raise NotFoundError(TEMPLATE_NOT_FOUND)
            source_import = await self._get_source_import(uow, source_import_id)
            previous = await uow.templates.get_version(template_id, template.latest_version)
            previous_definition = FormDefinition.model_validate(previous.definition_json)

            definition = normalize_definition(data, previous_definition)
            document_id = source_import_id or previous.source_import_id
            version = build_version(template, definition, template.latest_version + 1, document_id)
            template.latest_version = version.version
            template.name = definition.title
            await uow.templates.add_version(version)
            await self._record_corrections(uow, source_import, definition)
            return to_template_out(template, version)

        return await self._idempotency.execute(
            key=idempotency_key,
            scope=f"templates.{template_id}.versions.create",
            request_payload=self._request_payload(data, source_import_id),
            operation=operation,
            response_model=TemplateOut,
        )

    async def list_templates(self, limit: int, cursor: str | None) -> TemplatePageOut:
        """Página de plantillas. Se pide una fila de más para saber si hay otra página."""
        try:
            after = decode_cursor(cursor) if cursor else None
        except ValueError:
            raise ValidationError(INVALID_CURSOR, code="invalid_cursor") from None

        async with self._uow_factory() as uow:
            rows = await uow.templates.list_page(limit + 1, after)

        page = rows[:limit]
        has_more = len(rows) > limit
        next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if has_more else None
        return TemplatePageOut(items=[to_template_summary_out(row) for row in page], next_cursor=next_cursor)

    async def get_template(self, template_id: uuid.UUID) -> TemplateOut:
        async with self._uow_factory() as uow:
            row = await uow.templates.get_with_latest_version(template_id)
        if row is None:
            raise NotFoundError(TEMPLATE_NOT_FOUND)
        return to_template_out(*row)

    async def get_version(self, template_id: uuid.UUID, version: int) -> TemplateVersionOut:
        async with self._uow_factory() as uow:
            found = await uow.templates.get_version(template_id, version)
        if found is None:
            raise NotFoundError(f"La plantilla no tiene la versión {version}.")
        return to_version_out(found)
