import uuid

from app.domain.attachment_type import AttachmentType
from app.domain.document_types import FILE_EXTENSIONS, DocumentMimeType
from app.domain.response_status import ResponseStatus
from app.dto.responses import (
    AttachmentOut,
    AttachmentRecord,
    ResponseOut,
    ResponseRecord,
    ResponseSummaryOut,
)
from app.interfaces.storage_provider import StorageProvider
from app.models.attachment import Attachment
from app.models.form_response import FormResponse
from app.models.form_template_version import FormTemplateVersion


def build_response(version: FormTemplateVersion, name: str, job_demo_id: str | None = None) -> FormResponse:
    return FormResponse(
        id=uuid.uuid4(),
        template_id=version.template_id,
        template_version_id=version.id,
        job_demo_id=job_demo_id,
        name=name,
        status=ResponseStatus.DRAFT,
        values_json={},
    )


def attachment_file_key(response_id: uuid.UUID, upload_id: uuid.UUID, mime_type: DocumentMimeType) -> str:
    return f"responses/{response_id}/{upload_id}{FILE_EXTENSIONS[mime_type]}"


def build_attachment(
    response_id: uuid.UUID, field_id: str, filename: str, mime_type: DocumentMimeType, file_key: str
) -> Attachment:
    return Attachment(
        id=uuid.uuid4(),
        response_id=response_id,
        field_id=field_id,
        type=AttachmentType.PHOTO,
        file_key=file_key,
        filename=filename,
        mime_type=mime_type,
    )


def to_attachment_record(entity: Attachment) -> AttachmentRecord:
    return AttachmentRecord(
        id=entity.id,
        field_id=entity.field_id,
        filename=entity.filename,
        mime_type=entity.mime_type,
        file_key=entity.file_key,
        created_at=entity.created_at,
    )


def to_response_record(response: FormResponse, version: int, attachments: list[Attachment]) -> ResponseRecord:
    return ResponseRecord(
        id=response.id,
        template_id=response.template_id,
        template_version_id=response.template_version_id,
        version=version,
        job_demo_id=response.job_demo_id,
        name=response.name,
        status=response.status,
        values=response.values_json,
        attachments=[to_attachment_record(item) for item in attachments],
        submitted_at=response.submitted_at,
        created_at=response.created_at,
        updated_at=response.updated_at,
    )


async def to_attachment_out(record: AttachmentRecord, storage: StorageProvider) -> AttachmentOut:
    return AttachmentOut(**record.model_dump(exclude={"file_key"}), url=await storage.get_url(record.file_key))


async def to_response_out(record: ResponseRecord, storage: StorageProvider) -> ResponseOut:
    """Las URLs se firman aquí (sin llamadas de red), nunca se guardan."""
    attachments = [await to_attachment_out(item, storage) for item in record.attachments]
    return ResponseOut(**record.model_dump(exclude={"attachments"}), attachments=attachments)


def to_response_summary_out(response: FormResponse, version: int) -> ResponseSummaryOut:
    return ResponseSummaryOut(
        id=response.id,
        template_id=response.template_id,
        version=version,
        name=response.name,
        status=response.status,
        submitted_at=response.submitted_at,
        created_at=response.created_at,
        updated_at=response.updated_at,
    )
