import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.document_types import DocumentMimeType
from app.domain.import_status import ImportStatus


class ImportRecord(BaseModel):
    """Uso interno (se guarda en la respuesta idempotente). Lleva la key de S3, nunca sale al cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ImportStatus
    original_file_key: str
    original_filename: str
    mime_type: DocumentMimeType
    page_count: int | None = None
    warnings: list[Any] = Field(default_factory=list)
    draft_json: dict[str, Any] | None = None
    processing_started_at: datetime | None = None
    processing_finished_at: datetime | None = None
    processing_ms: int | None = None
    estimated_cost: Decimal | None = None
    detected_fields_count: int | None = None
    corrections_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ImportOut(BaseModel):
    """Respuesta al cliente. Sin original_file_key: solo la URL temporal."""

    id: uuid.UUID
    status: ImportStatus
    original_filename: str
    mime_type: DocumentMimeType
    page_count: int | None = None
    warnings: list[Any] = Field(default_factory=list)
    draft_json: dict[str, Any] | None = None
    processing_started_at: datetime | None = None
    processing_finished_at: datetime | None = None
    processing_ms: int | None = None
    estimated_cost: Decimal | None = None
    detected_fields_count: int | None = None
    corrections_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    # URL temporal para ver el archivo; se genera nueva en cada consulta
    original_url: str
