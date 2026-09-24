import asyncio
import uuid

from app.core.exceptions import NotFoundError, PayloadTooLargeError, ValidationError
from app.dto.imports import ImportOut, ImportRecord
from app.factories.import_factory import build_import, to_import_out, to_import_record
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkInterface
from app.services.idempotency_service import IdempotencyService
from app.utils.file_signatures import SIGNATURE_BYTES, detect_document_type
from app.utils.filenames import clean_filename
from app.utils.hashing import bytes_hash

BYTES_PER_MB = 1024 * 1024
IMPORT_NOT_FOUND = "No encontramos el documento original."


class ImportService:
    """Guarda el documento original (foto/PDF) en el storage y crea su registro en form_imports."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        idempotency: IdempotencyService,
        storage: StorageProvider,
        max_upload_bytes: int,
    ):
        self._uow_factory = uow_factory
        self._idempotency = idempotency
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes

    def _validate(self, content: bytes):
        if not content:
            raise ValidationError("El archivo está vacío.", code="empty_file")
        if len(content) > self._max_upload_bytes:
            max_mb = self._max_upload_bytes // BYTES_PER_MB
            raise PayloadTooLargeError(f"El archivo pesa más de {max_mb} MB. Elige uno más ligero.")
        mime_type = detect_document_type(content[:SIGNATURE_BYTES])
        if mime_type is None:
            raise ValidationError(
                "Solo se aceptan fotos (JPG, PNG o WEBP) o archivos PDF.", code="unsupported_file_type"
            )
        return mime_type

    async def create_import(self, filename: str | None, content: bytes, idempotency_key: str | None) -> ImportOut:
        mime_type = self._validate(content)
        name = clean_filename(filename)
        # El hash de un archivo grande usa CPU: se calcula fuera del hilo principal
        content_hash = await asyncio.to_thread(bytes_hash, content)

        async def operation(uow: UnitOfWorkInterface) -> ImportRecord:
            entity = build_import(name, mime_type)
            await self._storage.put(entity.original_file_key, content, mime_type)
            await uow.imports.add(entity)
            return to_import_record(entity)

        record = await self._idempotency.execute(
            key=idempotency_key,
            scope="imports.create",
            request_payload={"sha256": content_hash, "filename": name},
            operation=operation,
            response_model=ImportRecord,
        )
        return to_import_out(record, await self._storage.get_url(record.original_file_key))

    async def get_import(self, import_id: uuid.UUID) -> ImportOut:
        async with self._uow_factory() as uow:
            entity = await uow.imports.get(import_id)
        if entity is None:
            raise NotFoundError(IMPORT_NOT_FOUND)
        record = to_import_record(entity)
        return to_import_out(record, await self._storage.get_url(record.original_file_key))
