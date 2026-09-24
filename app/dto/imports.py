import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domain.document_types import DocumentMimeType
from app.domain.import_status import ImportStatus


class ImportRecord(BaseModel):
    """Uso interno (se guarda en la respuesta idempotente). Lleva la key de S3, nunca sale al cliente."""

    id: uuid.UUID
    status: ImportStatus
    original_file_key: str
    original_filename: str
    mime_type: DocumentMimeType
    created_at: datetime


class ImportOut(BaseModel):
    id: uuid.UUID
    status: ImportStatus
    original_filename: str
    mime_type: DocumentMimeType
    created_at: datetime
    # URL temporal para ver el archivo; se genera nueva en cada consulta
    original_url: str
