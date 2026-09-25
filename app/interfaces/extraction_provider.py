from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.domain.document_types import DocumentMimeType
from app.dto.form_definition import FormDefinitionInput


@dataclass(frozen=True)
class ExtractionInput:
    """Documento original que se entrega al proveedor de extracción."""

    filename: str
    mime_type: DocumentMimeType
    content: bytes


@dataclass(frozen=True)
class ExtractionWarning:
    """Advertencia recuperable que el front puede mostrar durante la revisión humana."""

    code: str
    message: str
    field_id: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"code": self.code, "message": self.message, "field_id": self.field_id}


@dataclass(frozen=True)
class ExtractionResult:
    """Resultado neutral; no expone objetos propios de OpenAI al resto de la aplicación."""

    definition: FormDefinitionInput | None
    warnings: list[ExtractionWarning]
    estimated_cost: Decimal | None


class ExtractionProviderError(Exception):
    """Error técnico del proveedor, con un código/mensaje seguro para persistir."""

    def __init__(self, code: str, public_message: str):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


class ExtractionProvider(Protocol):
    async def extract(self, source: ExtractionInput) -> ExtractionResult: ...
