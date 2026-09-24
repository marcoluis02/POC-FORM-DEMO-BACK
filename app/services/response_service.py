import asyncio
import logging
import uuid

from app.core.exceptions import ConflictError, DomainError, NotFoundError, ValidationError
from app.domain.answer_rules import PHOTO_MIME_TYPES
from app.domain.response_status import ResponseStatus
from app.domain.worker_task_type import WorkerTaskType
from app.dto.form_definition import FieldDefinition, FormDefinition
from app.dto.responses import (
    AttachmentDeletedOut,
    AttachmentOut,
    AttachmentRecord,
    ResponseCreateIn,
    ResponseOut,
    ResponsePageOut,
    ResponseRecord,
    ResponseValuesIn,
)
from app.factories.response_factory import (
    attachment_file_key,
    build_attachment,
    build_response,
    to_attachment_out,
    to_attachment_record,
    to_response_out,
    to_response_record,
    to_response_summary_out,
)
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkInterface
from app.models.form_response import FormResponse
from app.models.form_template_version import FormTemplateVersion
from app.services.answer_validator import accepts_photos, clean_values, fields_by_id, missing_required
from app.services.idempotency_service import IdempotencyService
from app.services.template_service import INVALID_CURSOR, TEMPLATE_NOT_FOUND
from app.services.upload_validation import check_upload
from app.services.worker_task_service import enqueue_task
from app.utils.cursor import decode_cursor, encode_cursor
from app.utils.filenames import clean_filename
from app.utils.hashing import bytes_hash, stable_hash
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

RESPONSE_NOT_FOUND = "No encontramos este formulario."
ALREADY_SUBMITTED = "Este formulario ya fue enviado y no se puede cambiar."
INVALID_ANSWERS = "Hay respuestas que debes revisar."
INCOMPLETE = "Faltan preguntas obligatorias por contestar."
FIELD_NOT_FOUND = "Esta pregunta no existe en el formulario."
FIELD_WITHOUT_PHOTOS = "Esta pregunta no acepta fotos."
UNSUPPORTED_PHOTO = "Solo se aceptan fotos JPG, PNG o WEBP."
ATTACHMENT_NOT_FOUND = "No encontramos esta foto."
# Base para sacar siempre el mismo nombre de archivo cuando se reintenta la misma subida
UPLOAD_NAMESPACE = uuid.UUID("6f1c2a54-9d3e-4b7a-8c21-5e0f3d9a7b61")

LockedRow = tuple[FormResponse, FormTemplateVersion]


class ResponseService:
    """Formularios llenados: borrador, fotos y envío. Las reglas de cada respuesta están en answer_validator."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        idempotency: IdempotencyService,
        storage: StorageProvider,
        max_upload_bytes: int,
        max_photos_per_field: int,
    ):
        self._uow_factory = uow_factory
        self._idempotency = idempotency
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes
        self._max_photos_per_field = max_photos_per_field

    # ---------- Reglas comunes ----------

    @staticmethod
    def _ensure_draft(row: LockedRow | None) -> LockedRow:
        if row is None:
            raise NotFoundError(RESPONSE_NOT_FOUND)
        if row[0].status == ResponseStatus.SUBMITTED:
            raise ConflictError(ALREADY_SUBMITTED, code="response_already_submitted")
        return row

    @staticmethod
    def _clean_or_fail(definition: FormDefinition, data: ResponseValuesIn) -> dict:
        cleaned, errors = clean_values(definition, data.values)
        if errors:
            raise ValidationError(INVALID_ANSWERS, code="invalid_answers", details=errors)
        return cleaned

    def _photo_field(self, version: FormTemplateVersion, field_id: str) -> FieldDefinition:
        field = fields_by_id(FormDefinition.model_validate(version.definition_json)).get(field_id)
        if field is None:
            raise ValidationError(FIELD_NOT_FOUND, code="unknown_field")
        if not accepts_photos(field):
            raise ValidationError(FIELD_WITHOUT_PHOTOS, code="field_without_photos")
        return field

    async def _ensure_photo_slot(self, uow: UnitOfWorkInterface, response_id: uuid.UUID, field_id: str) -> None:
        if await uow.attachments.count_for_field(response_id, field_id) >= self._max_photos_per_field:
            raise ValidationError(
                f"Esta pregunta ya tiene {self._max_photos_per_field} fotos. Quita una para agregar otra.",
                code="too_many_photos",
            )

    # ---------- Crear, consultar y listar ----------

    async def create_response(self, data: ResponseCreateIn, idempotency_key: str | None) -> ResponseOut:
        """Empieza un formulario en borrador con la última versión de la plantilla."""

        async def operation(uow: UnitOfWorkInterface) -> ResponseRecord:
            row = await uow.templates.get_with_latest_version(data.template_id)
            if row is None:
                raise NotFoundError(TEMPLATE_NOT_FOUND)
            _, version = row
            response = build_response(version, data.name)
            await uow.responses.add(response)
            return to_response_record(response, version.version, [])

        record = await self._idempotency.execute(
            key=idempotency_key,
            scope="responses.create",
            request_payload=data.model_dump(mode="json"),
            operation=operation,
            response_model=ResponseRecord,
        )
        return await to_response_out(record, self._storage)

    async def get_response(self, response_id: uuid.UUID) -> ResponseOut:
        async with self._uow_factory() as uow:
            row = await uow.responses.get_with_version_number(response_id)
            if row is None:
                raise NotFoundError(RESPONSE_NOT_FOUND)
            attachments = await uow.attachments.list_for_response(response_id)
        return await to_response_out(to_response_record(row[0], row[1], attachments), self._storage)

    async def list_responses(self, template_id: uuid.UUID, limit: int, cursor: str | None) -> ResponsePageOut:
        """Página de formularios llenados de una plantilla. Se pide una fila de más para saber si hay otra."""
        try:
            after = decode_cursor(cursor) if cursor else None
        except ValueError:
            raise ValidationError(INVALID_CURSOR, code="invalid_cursor") from None

        async with self._uow_factory() as uow:
            if await uow.templates.get(template_id) is None:
                raise NotFoundError(TEMPLATE_NOT_FOUND)
            rows = await uow.responses.list_page(template_id, limit + 1, after)

        page = rows[:limit]
        has_more = len(rows) > limit
        next_cursor = encode_cursor(page[-1][0].created_at, page[-1][0].id) if has_more else None
        return ResponsePageOut(
            items=[to_response_summary_out(response, version) for response, version in page],
            next_cursor=next_cursor,
        )

    # ---------- Borrador y envío ----------

    async def save_draft(
        self, response_id: uuid.UUID, data: ResponseValuesIn, idempotency_key: str | None
    ) -> ResponseOut:
        """Guarda las respuestas tal como están. Revisa el tipo de cada una pero no exige las obligatorias."""

        async def operation(uow: UnitOfWorkInterface) -> ResponseRecord:
            response, version = self._ensure_draft(await uow.responses.get_with_version(response_id, lock=True))
            response.name = data.name
            response.values_json = self._clean_or_fail(FormDefinition.model_validate(version.definition_json), data)
            await uow.responses.update(response)
            attachments = await uow.attachments.list_for_response(response_id)
            return to_response_record(response, version.version, attachments)

        record = await self._idempotency.execute(
            key=idempotency_key,
            scope=f"responses.{response_id}.draft",
            request_payload=data.model_dump(mode="json"),
            operation=operation,
            response_model=ResponseRecord,
        )
        return await to_response_out(record, self._storage)

    async def submit(self, response_id: uuid.UUID, data: ResponseValuesIn, idempotency_key: str | None) -> ResponseOut:
        """Guarda las respuestas finales y envía. Si falta una obligatoria no se guarda nada (422)."""

        async def operation(uow: UnitOfWorkInterface) -> ResponseRecord:
            response, version = self._ensure_draft(await uow.responses.get_with_version(response_id, lock=True))
            definition = FormDefinition.model_validate(version.definition_json)
            values = self._clean_or_fail(definition, data)
            attachments = await uow.attachments.list_for_response(response_id)
            missing = missing_required(definition, values, {item.field_id for item in attachments})
            if missing:
                raise ValidationError(INCOMPLETE, code="response_incomplete", details=missing)

            response.name = data.name
            response.values_json = values
            response.status = ResponseStatus.SUBMITTED
            response.submitted_at = utc_now()
            await uow.responses.update(response)
            return to_response_record(response, version.version, attachments)

        record = await self._idempotency.execute(
            key=idempotency_key,
            scope=f"responses.{response_id}.submit",
            request_payload=data.model_dump(mode="json"),
            operation=operation,
            response_model=ResponseRecord,
        )
        return await to_response_out(record, self._storage)

    # ---------- Fotos ----------

    @staticmethod
    def _upload_id(idempotency_key: str | None, request_payload: dict) -> uuid.UUID:
        """Con Idempotency-Key el reintento usa el mismo nombre en S3 y no deja archivos repetidos."""
        if idempotency_key is None:
            return uuid.uuid4()
        return uuid.uuid5(UPLOAD_NAMESPACE, f"{idempotency_key}:{stable_hash(request_payload)}")

    async def _discard_file(self, file_key: str) -> None:
        """El archivo ya subió pero no se registró: el worker lo borra de S3."""
        try:
            async with self._uow_factory() as uow:
                await enqueue_task(uow, WorkerTaskType.DELETE_STORAGE_OBJECT, {"key": file_key})
                await uow.commit()
        except Exception:
            logger.exception("No se pudo programar el borrado de %s", file_key)

    async def add_attachment(
        self,
        response_id: uuid.UUID,
        field_id: str,
        filename: str | None,
        content: bytes,
        idempotency_key: str | None,
    ) -> AttachmentOut:
        """Sube la foto a S3 sin tener abierta una conexión a la BD y después la registra."""
        mime_type = check_upload(content, self._max_upload_bytes, PHOTO_MIME_TYPES, UNSUPPORTED_PHOTO)
        name = clean_filename(filename)
        content_hash = await asyncio.to_thread(bytes_hash, content)
        request_payload = {"field_id": field_id, "sha256": content_hash, "filename": name}

        # Revisión rápida antes de subir, para no mandar a S3 algo que se va a rechazar
        async with self._uow_factory() as uow:
            _, version = self._ensure_draft(await uow.responses.get_with_version(response_id))
            self._photo_field(version, field_id)
            await self._ensure_photo_slot(uow, response_id, field_id)

        upload_id = self._upload_id(idempotency_key, request_payload)
        file_key = attachment_file_key(response_id, upload_id, mime_type)
        await self._storage.put(file_key, content, mime_type)

        async def operation(uow: UnitOfWorkInterface) -> AttachmentRecord:
            # Se revisa otra vez con la fila bloqueada: pudo cambiar mientras subía el archivo
            _, locked_version = self._ensure_draft(await uow.responses.get_with_version(response_id, lock=True))
            self._photo_field(locked_version, field_id)
            await self._ensure_photo_slot(uow, response_id, field_id)
            attachment = build_attachment(response_id, field_id, name, mime_type, file_key)
            await uow.attachments.add(attachment)
            return to_attachment_record(attachment)

        try:
            record = await self._idempotency.execute(
                key=idempotency_key,
                scope=f"responses.{response_id}.attachments.create",
                request_payload=request_payload,
                operation=operation,
                response_model=AttachmentRecord,
            )
        except DomainError:
            await self._discard_file(file_key)
            raise
        return await to_attachment_out(record, self._storage)

    async def delete_attachment(
        self, response_id: uuid.UUID, attachment_id: uuid.UUID, idempotency_key: str | None
    ) -> AttachmentDeletedOut:
        """Quita la foto de la respuesta al momento; el archivo de S3 lo borra el worker después."""

        async def operation(uow: UnitOfWorkInterface) -> AttachmentDeletedOut:
            self._ensure_draft(await uow.responses.get_with_version(response_id, lock=True))
            attachment = await uow.attachments.get_for_response(response_id, attachment_id)
            if attachment is None:
                raise NotFoundError(ATTACHMENT_NOT_FOUND)
            await uow.attachments.delete(attachment)
            await enqueue_task(uow, WorkerTaskType.DELETE_STORAGE_OBJECT, {"key": attachment.file_key})
            return AttachmentDeletedOut(id=attachment_id)

        return await self._idempotency.execute(
            key=idempotency_key,
            scope=f"responses.{response_id}.attachments.delete",
            request_payload={"attachment_id": str(attachment_id)},
            operation=operation,
            response_model=AttachmentDeletedOut,
        )
