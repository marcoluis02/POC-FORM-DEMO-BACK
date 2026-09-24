from io import BytesIO

from pypdf import PdfWriter

# Primeros bytes reales de una imagen PNG
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
BLANK_PAGE_SIZE = 200


def make_pdf(pages: int, password: str | None = None) -> bytes:
    """PDF real con páginas en blanco. Con password queda protegido."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=BLANK_PAGE_SIZE, height=BLANK_PAGE_SIZE)
    if password:
        writer.encrypt(password)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
