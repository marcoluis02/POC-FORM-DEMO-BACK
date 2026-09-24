import pytest

from app.domain.document_types import DocumentMimeType
from app.utils.file_signatures import detect_document_type
from app.utils.filenames import clean_filename


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"\xff\xd8\xff\xe0" + b"\x00" * 8, DocumentMimeType.JPEG),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 4, DocumentMimeType.PNG),
        (b"RIFF\x00\x00\x00\x00WEBP", DocumentMimeType.WEBP),
        (b"%PDF-1.7\n" + b"\x00" * 3, DocumentMimeType.PDF),
    ],
)
def test_detecta_el_tipo_por_los_primeros_bytes(head, expected):
    assert detect_document_type(head) == expected


@pytest.mark.parametrize("head", [b"", b"hola mundo!!", b"RIFF\x00\x00\x00\x00WAVE", b"MZ\x90\x00"])
def test_no_acepta_otros_archivos(head):
    assert detect_document_type(head) is None


def test_limpia_rutas_y_caracteres_raros_del_nombre():
    assert clean_filename("C:\\fotos\\../revisión 1.jpg") == "revisión 1.jpg"
    assert clean_filename("../../etc/passwd") == "passwd"
    assert clean_filename("<script>.pdf") == "script.pdf"


def test_usa_un_nombre_por_defecto_si_no_queda_nada():
    assert clean_filename(None) == "documento"
    assert clean_filename("   ") == "documento"
    assert clean_filename("///") == "documento"


def test_corta_nombres_muy_largos():
    assert len(clean_filename("a" * 400 + ".pdf")) <= 255
