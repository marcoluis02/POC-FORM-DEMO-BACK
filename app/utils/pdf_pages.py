from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError


class ProtectedPdfError(Exception):
    pass


class UnreadablePdfError(Exception):
    pass


def count_pdf_pages(content: bytes) -> int:
    """Cuenta las páginas sin leer su contenido. Usa CPU: llamarla con asyncio.to_thread."""
    try:
        return len(PdfReader(BytesIO(content)).pages)
    except FileNotDecryptedError as error:
        raise ProtectedPdfError() from error
    except Exception as error:
        # El archivo viene del cliente: cualquier falla al leerlo se toma como PDF dañado
        raise UnreadablePdfError() from error
