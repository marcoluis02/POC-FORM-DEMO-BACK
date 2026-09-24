import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domain.template_status import TemplateStatus
from app.dto.form_definition import FormDefinition


class TemplateVersionOut(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    version: int
    definition: FormDefinition
    source_import_id: uuid.UUID | None
    created_at: datetime


class TemplateSummaryOut(BaseModel):
    id: uuid.UUID
    name: str
    status: TemplateStatus
    latest_version: int
    created_at: datetime
    updated_at: datetime


class TemplateOut(TemplateSummaryOut):
    current_version: TemplateVersionOut


class TemplatePageOut(BaseModel):
    items: list[TemplateSummaryOut]
    next_cursor: str | None
