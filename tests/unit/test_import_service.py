import uuid

import pytest

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    StorageUnavailableError,
    ValidationError,
)
from tests.conftest import PDF_BYTES, PNG_BYTES, TEST_MAX_PDF_PAGES, TEST_MAX_UPLOAD_BYTES
from tests.fakes.sample_files import make_pdf


async def test_guarda_el_archivo_y_crea_el_registro(import_service, fake_storage, fake_db):
    result = await import_service.create_import("revision.png", PNG_BYTES, None)

    assert result.mime_type == "image/png"
    assert result.original_filename == "revision.png"
    assert result.status == "received"
    stored_key = f"imports/{result.id}/original.png"
    assert fake_storage.objects[stored_key] == (PNG_BYTES, "image/png")
    assert result.original_url.startswith(f"https://storage.test/{stored_key}")
    assert fake_db.imports[result.id].original_file_key == stored_key


async def test_el_tipo_sale_del_contenido_y_no_del_nombre(import_service):
    result = await import_service.create_import("foto.jpg", PDF_BYTES, None)

    assert result.mime_type == "application/pdf"


async def test_rechaza_archivo_vacio(import_service):
    with pytest.raises(ValidationError) as error:
        await import_service.create_import("vacio.pdf", b"", None)

    assert error.value.code == "empty_file"


async def test_rechaza_archivo_muy_pesado(import_service, fake_storage):
    with pytest.raises(PayloadTooLargeError):
        await import_service.create_import("grande.pdf", PDF_BYTES + b"\x00" * TEST_MAX_UPLOAD_BYTES, None)

    assert fake_storage.put_calls == 0


async def test_rechaza_tipos_no_permitidos(import_service, fake_storage):
    with pytest.raises(ValidationError) as error:
        await import_service.create_import("virus.exe", b"MZ\x90\x00" + b"\x00" * 20, None)

    assert error.value.code == "unsupported_file_type"
    assert fake_storage.put_calls == 0


async def test_acepta_pdf_con_el_maximo_de_paginas(import_service):
    result = await import_service.create_import("tres.pdf", make_pdf(pages=TEST_MAX_PDF_PAGES), None)

    assert result.mime_type == "application/pdf"


async def test_rechaza_pdf_con_demasiadas_paginas(import_service, fake_storage):
    with pytest.raises(ValidationError) as error:
        await import_service.create_import("largo.pdf", make_pdf(pages=TEST_MAX_PDF_PAGES + 1), None)

    assert error.value.code == "pdf_too_many_pages"
    assert str(TEST_MAX_PDF_PAGES + 1) in error.value.message
    assert fake_storage.put_calls == 0


async def test_rechaza_pdf_con_contrasena(import_service):
    with pytest.raises(ValidationError) as error:
        await import_service.create_import("secreto.pdf", make_pdf(pages=1, password="secreto"), None)

    assert error.value.code == "pdf_protected"


async def test_rechaza_pdf_danado_aunque_empiece_como_pdf(import_service):
    with pytest.raises(ValidationError) as error:
        await import_service.create_import("roto.pdf", b"%PDF-1.7\n" + b"\x00" * 64, None)

    assert error.value.code == "pdf_unreadable"


async def test_reintento_con_la_misma_llave_no_sube_dos_veces(import_service, fake_storage, fake_db):
    first = await import_service.create_import("revision.png", PNG_BYTES, "llave-subida-1")
    second = await import_service.create_import("revision.png", PNG_BYTES, "llave-subida-1")

    assert first.id == second.id
    assert fake_storage.put_calls == 1
    assert len(fake_db.imports) == 1


async def test_misma_llave_con_otro_archivo_da_conflicto(import_service):
    await import_service.create_import("revision.png", PNG_BYTES, "llave-subida-2")

    with pytest.raises(ConflictError) as error:
        await import_service.create_import("otro.pdf", PDF_BYTES, "llave-subida-2")

    assert error.value.code == "idempotency_key_reused"


async def test_si_s3_falla_no_se_crea_el_registro(import_service, fake_storage, fake_db):
    fake_storage.fail = True

    with pytest.raises(StorageUnavailableError):
        await import_service.create_import("revision.png", PNG_BYTES, None)

    assert fake_db.imports == {}


async def test_consulta_regresa_una_url_nueva(import_service):
    created = await import_service.create_import("revision.png", PNG_BYTES, None)

    found = await import_service.get_import(created.id)

    assert found.id == created.id
    assert found.original_url.startswith("https://storage.test/")


async def test_consulta_de_un_documento_que_no_existe(import_service):
    with pytest.raises(NotFoundError):
        await import_service.get_import(uuid.uuid4())
