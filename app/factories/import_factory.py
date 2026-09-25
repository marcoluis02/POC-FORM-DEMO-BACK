import uuid

from app.domain.document_types import FILE_EXTENSIONS, DocumentMimeType
from app.domain.import_status import ImportStatus
from app.dto.imports import ImportOut, ImportRecord
from app.models.form_import import FormImport


def build_import(filename: str, mime_type: DocumentMimeType, page_count: int) -> FormImport:
    import_id = uuid.uuid4()
    return FormImport(
        id=import_id,
        status=ImportStatus.RECEIVED,
        original_file_key=f"imports/{import_id}/original{FILE_EXTENSIONS[mime_type]}",
        original_filename=filename,
        mime_type=mime_type,
        page_count=page_count,
        warnings=[],
    )


def to_import_record(entity: FormImport) -> ImportRecord:
    return ImportRecord.model_validate(entity)


def to_import_out(record: ImportRecord, original_url: str) -> ImportOut:
    return ImportOut(
        **record.model_dump(exclude={"original_file_key"}),
        original_url=original_url,
    )
