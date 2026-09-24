from enum import StrEnum


class DocumentMimeType(StrEnum):
    """Tipos de documento original que se aceptan (foto o PDF del formato en papel)."""

    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"
    PDF = "application/pdf"


FILE_EXTENSIONS: dict[DocumentMimeType, str] = {
    DocumentMimeType.JPEG: ".jpg",
    DocumentMimeType.PNG: ".png",
    DocumentMimeType.WEBP: ".webp",
    DocumentMimeType.PDF: ".pdf",
}
