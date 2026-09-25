import asyncio
import logging
import uuid

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.document_types import DocumentMimeType
from app.domain.worker_task_type import WorkerTaskType
from app.dto.imports import ImportOut, ImportRecord
from app.factories.import_factory import build_import, to_import_out, to_import_record
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkInterface
from app.services.idempotency_service import IdempotencyService
from app.services.upload_validation import check_upload
from app.services.worker_task_service import enqueue_task
from app.utils.filenames import clean_filename
from app.utils.hashing import bytes_hash, stable_hash
from app.utils.pdf_pages import ProtectedPdfError, UnreadablePdfError, count_pdf_pages
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

IMPORT_NOT_FOUND = "No encontramos el documento original."
UNSUPPORTED_DOCUMENT = "Solo se aceptan fotos (JPG, PNG o WEBP) o archivos PDF."


class ImportService:
    """Guarda el documento original (foto/PDF) en el storage y crea su registro en form_imports."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        idempotency: IdempotencyService,
        storage: StorageProvider,
        max_upload_bytes: int,
        max_pdf_pages: int,
    ):
        self._uow_factory = uow_factory
        self._idempotency = idempotency
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes
        self._max_pdf_pages = max_pdf_pages

    async def _discard_file(self, file_key: str) -> None:
        """El archivo ya subió pero no se registró: se borra de S3 al momento."""
        try:
            await self._storage.delete(file_key)
        except Exception:
            logger.exception("No se pudo borrar el archivo huérfano %s", file_key)

    async def _validate_pdf_pages(self, content: bytes) -> int:
        try:
            pages = await asyncio.to_thread(count_pdf_pages, content)
        except ProtectedPdfError:
            raise ValidationError(
                "El PDF tiene contraseña. Súbelo sin contraseña.", code="pdf_protected"
            ) from None
        except UnreadablePdfError:
            raise ValidationError("No pudimos leer el PDF. Puede estar dañado.", code="pdf_unreadable") from None
        if pages == 0:
            raise ValidationError("El PDF no tiene páginas.", code="pdf_unreadable")
        if pages > self._max_pdf_pages:
            raise ValidationError(
                f"El PDF tiene {pages} páginas. El máximo es {self._max_pdf_pages}.", code="pdf_too_many_pages"
            )
        return pages

    async def _validate(self, content: bytes) -> tuple[DocumentMimeType, int]:
        """El tipo, el tamaño y las páginas se revisan aquí con el archivo real.
        Lo que diga el navegador (nombre, Content-Type) no se toma en cuenta."""
        mime_type = check_upload(content, self._max_upload_bytes, DocumentMimeType, UNSUPPORTED_DOCUMENT)
        page_count = await self._validate_pdf_pages(content) if mime_type == DocumentMimeType.PDF else 1
        return mime_type, page_count

    async def create_import(self, filename: str | None, content: bytes, idempotency_key: str | None) -> ImportOut:
        mime_type, page_count = await self._validate(content)
        name = clean_filename(filename)
        # El hash de un archivo grande usa CPU: se calcula fuera del hilo principal
        content_hash = await asyncio.to_thread(bytes_hash, content)
        request_payload = {"sha256": content_hash, "filename": name}

        # Si ya se guardó con esta llave, no se vuelve a subir a S3
        if idempotency_key is not None:
            async with self._uow_factory() as uow:
                stored = await uow.idempotency.get_active(idempotency_key, "imports.create", utc_now())
            if stored is not None:
                record = IdempotencyService._replay(stored, stable_hash(request_payload), ImportRecord)
                return to_import_out(record, await self._storage.get_url(record.original_file_key))

        entity = build_import(name, mime_type, page_count)

        # Primero S3, luego BD. Si la BD falla, se borra el archivo para no dejarlo huérfano.
        await self._storage.put(entity.original_file_key, content, mime_type)

        async def operation(uow: UnitOfWorkInterface) -> ImportRecord:
            await uow.imports.add(entity)
            await enqueue_task(
                uow,
                WorkerTaskType.EXTRACT_IMPORT,
                {"import_id": str(entity.id)},
                dedupe_key=f"extract_import:{entity.id}",
            )
            return to_import_record(entity)

        try:
            record = await self._idempotency.execute(
                key=idempotency_key,
                scope="imports.create",
                request_payload=request_payload,
                operation=operation,
                response_model=ImportRecord,
            )
        except Exception:
            await self._discard_file(entity.original_file_key)
            raise

        # Carrera rara: otra petición guardó primero y este put quedó de más
        if record.original_file_key != entity.original_file_key:
            await self._discard_file(entity.original_file_key)

        return to_import_out(record, await self._storage.get_url(record.original_file_key))

    async def get_import(self, import_id: uuid.UUID) -> ImportOut:
        async with self._uow_factory() as uow:
            entity = await uow.imports.get(import_id)
        if entity is None:
            raise NotFoundError(IMPORT_NOT_FOUND)
        record = to_import_record(entity)
        return to_import_out(record, await self._storage.get_url(record.original_file_key))
