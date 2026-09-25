import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.document_types import DocumentMimeType
from app.domain.response_status import ResponseStatus
from app.dto.form_definition import FIELD_ID_PATTERN, MAX_FIELDS_PER_SECTION, MAX_SECTIONS, TITLE_MAX_LENGTH

# Nunca puede haber más respuestas que preguntas en una plantilla
MAX_VALUES = MAX_SECTIONS * MAX_FIELDS_PER_SECTION
RESPONSE_NAME_MAX_LENGTH = TITLE_MAX_LENGTH


class ResponseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    template_id: uuid.UUID
    name: str = Field(min_length=1, max_length=RESPONSE_NAME_MAX_LENGTH)


class ResponseValuesIn(BaseModel):
    """Respuestas por id de pregunta: { "f_001": "yes", "f_002": 72.5 }.
    Una pregunta sin contestar se puede mandar como null o no mandarse.
    name: cómo se llama este llenado en el listado."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=RESPONSE_NAME_MAX_LENGTH)
    values: dict[str, Any] = Field(max_length=MAX_VALUES)

    @field_validator("values", mode="before")
    @classmethod
    def values_must_be_field_map(cls, value):
        if not isinstance(value, dict):
            raise ValueError("values debe ser un objeto con respuestas por id de pregunta.")
        malformed = [key for key in value if not isinstance(key, str) or re.fullmatch(FIELD_ID_PATTERN, key) is None]
        if malformed:
            raise ValueError("values contiene ids de pregunta con formato inválido.")
        return value


class AttachmentRecord(BaseModel):
    """Uso interno. Lleva la key de S3, nunca sale al cliente."""

    id: uuid.UUID
    field_id: str
    filename: str
    mime_type: DocumentMimeType
    file_key: str
    created_at: datetime


class AttachmentOut(BaseModel):
    id: uuid.UUID
    field_id: str
    filename: str
    mime_type: DocumentMimeType
    created_at: datetime
    # URL temporal para ver la foto; se genera nueva en cada consulta
    url: str


class AttachmentDeletedOut(BaseModel):
    id: uuid.UUID


class ResponseRecord(BaseModel):
    """Uso interno (se guarda en la respuesta idempotente) con las fotos sin URL."""

    id: uuid.UUID
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    version: int
    name: str
    status: ResponseStatus
    values: dict[str, Any]
    attachments: list[AttachmentRecord]
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResponseOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    template_version_id: uuid.UUID
    version: int
    name: str
    status: ResponseStatus
    values: dict[str, Any]
    attachments: list[AttachmentOut]
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResponseSummaryOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    version: int
    name: str
    status: ResponseStatus
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResponsePageOut(BaseModel):
    items: list[ResponseSummaryOut]
    next_cursor: str | None
