from app.domain.document_types import DocumentMimeType

# Se revisan los primeros bytes del archivo: el nombre y el Content-Type los puede inventar el cliente
SIGNATURE_BYTES = 12


def detect_document_type(head: bytes) -> DocumentMimeType | None:
    if head.startswith(b"\xff\xd8\xff"):
        return DocumentMimeType.JPEG
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return DocumentMimeType.PNG
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return DocumentMimeType.WEBP
    if head.startswith(b"%PDF-"):
        return DocumentMimeType.PDF
    return None
