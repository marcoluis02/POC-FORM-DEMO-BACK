import asyncio
import uuid

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.document_types import DocumentMimeType
from app.dto.imports import ImportOut, ImportRecord
from app.factories.import_factory import build_import, to_import_out, to_import_record
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkInterface
from app.services.idempotency_service import IdempotencyService
from app.services.upload_validation import check_upload
from app.utils.filenames import clean_filename
from app.utils.hashing import bytes_hash
from app.utils.pdf_pages import ProtectedPdfError, UnreadablePdfError, count_pdf_pages

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

    async def _validate_pdf_pages(self, content: bytes) -> None:
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

    async def _validate(self, content: bytes) -> DocumentMimeType:
        """El tipo, el tamaño y las páginas se revisan aquí con el archivo real.
        Lo que diga el navegador (nombre, Content-Type) no se toma en cuenta."""
        mime_type = check_upload(content, self._max_upload_bytes, DocumentMimeType, UNSUPPORTED_DOCUMENT)
        if mime_type == DocumentMimeType.PDF:
            await self._validate_pdf_pages(content)
        return mime_type

    async def create_import(self, filename: str | None, content: bytes, idempotency_key: str | None) -> ImportOut:
        mime_type = await self._validate(content)
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
