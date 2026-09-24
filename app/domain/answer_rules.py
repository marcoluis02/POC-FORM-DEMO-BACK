from enum import StrEnum

from app.domain.document_types import DocumentMimeType
from app.domain.field_types import FieldType

SHORT_TEXT_MAX_LENGTH = 500
LONG_TEXT_MAX_LENGTH = 5000
# Tope razonable para que un número no rompa reportes ni sumas
NUMBER_MAX_ABS = 1_000_000_000_000
DATE_FORMAT = "%Y-%m-%d"


class YesNoNa(StrEnum):
    YES = "yes"
    NO = "no"
    NA = "na"


# La respuesta de estos campos no va en values: son las fotos adjuntas (photo)
# o todavía no se captura en la POC (firma)
NO_VALUE_FIELD_TYPES = frozenset({FieldType.PHOTO, FieldType.SIGNATURE_PLACEHOLDER})

# La firma es solo un espacio reservado en la POC: nunca se exige al enviar
NOT_REQUIRED_ON_SUBMIT = frozenset({FieldType.SIGNATURE_PLACEHOLDER})

# Fotos de respuestas y evidencias: solo imágenes (el PDF solo aplica al documento original)
PHOTO_MIME_TYPES = frozenset({DocumentMimeType.JPEG, DocumentMimeType.PNG, DocumentMimeType.WEBP})
