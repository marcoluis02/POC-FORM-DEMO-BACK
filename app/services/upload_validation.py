from collections.abc import Collection

from app.core.exceptions import PayloadTooLargeError, ValidationError
from app.domain.document_types import DocumentMimeType
from app.utils.file_signatures import SIGNATURE_BYTES, detect_document_type

BYTES_PER_MB = 1024 * 1024


def check_upload(
    content: bytes, max_bytes: int, allowed: Collection[DocumentMimeType], unsupported_message: str
) -> DocumentMimeType:
    """Revisa el archivo real: que no esté vacío, su tamaño y su tipo por los primeros bytes.
    El nombre y el Content-Type que manda el navegador no se toman en cuenta."""
    if not content:
        raise ValidationError("El archivo está vacío.", code="empty_file")
    if len(content) > max_bytes:
        raise PayloadTooLargeError(f"El archivo pesa más de {max_bytes // BYTES_PER_MB} MB. Elige uno más ligero.")
    mime_type = detect_document_type(content[:SIGNATURE_BYTES])
    if mime_type is None or mime_type not in allowed:
        raise ValidationError(unsupported_message, code="unsupported_file_type")
    return mime_type
