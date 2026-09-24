import uuid

import pytest

from app.core.config import get_settings
from app.factories.services_factory import get_import_service, get_template_service
from app.main import app
from tests.conftest import PDF_BYTES, PNG_BYTES

IMPORTS_URL = f"{get_settings().api_prefix}/imports"
TEMPLATES_URL = f"{get_settings().api_prefix}/templates"


@pytest.fixture(autouse=True)
def use_fake_services(import_service, template_service):
    app.dependency_overrides[get_import_service] = lambda: import_service
    app.dependency_overrides[get_template_service] = lambda: template_service


async def test_sube_el_documento_original(client):
    response = await client.post(IMPORTS_URL, files={"file": ("revision.pdf", PDF_BYTES, "application/pdf")})

    assert response.status_code == 201
    body = response.json()
    assert body["mime_type"] == "application/pdf"
    assert body["original_filename"] == "revision.pdf"
    assert body["original_url"].startswith("https://storage.test/")
    assert "original_file_key" not in body


async def test_rechaza_archivos_que_no_son_foto_ni_pdf(client):
    response = await client.post(IMPORTS_URL, files={"file": ("notas.txt", b"hola mundo, soy texto", "text/plain")})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_file_type"


async def test_sin_archivo_da_422(client):
    response = await client.post(IMPORTS_URL)

    assert response.status_code == 422


async def test_reintento_con_la_misma_llave_regresa_el_mismo_documento(client, fake_storage):
    files = {"file": ("revision.png", PNG_BYTES, "image/png")}
    headers = {"Idempotency-Key": "subida-api-1"}

    first = await client.post(IMPORTS_URL, files=files, headers=headers)
    second = await client.post(IMPORTS_URL, files=files, headers=headers)

    assert first.json()["id"] == second.json()["id"]
    assert fake_storage.put_calls == 1


async def test_consulta_el_documento(client):
    created = (await client.post(IMPORTS_URL, files={"file": ("r.png", PNG_BYTES, "image/png")})).json()

    response = await client.get(f"{IMPORTS_URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_consulta_de_documento_inexistente_da_404(client):
    response = await client.get(f"{IMPORTS_URL}/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_la_plantilla_queda_ligada_al_documento(client, maintenance_template):
    document = (await client.post(IMPORTS_URL, files={"file": ("r.png", PNG_BYTES, "image/png")})).json()

    response = await client.post(TEMPLATES_URL, params={"source_import_id": document["id"]}, json=maintenance_template)

    assert response.status_code == 201
    assert response.json()["current_version"]["source_import_id"] == document["id"]


async def test_plantilla_con_documento_inexistente_da_422(client, maintenance_template):
    response = await client.post(TEMPLATES_URL, params={"source_import_id": str(uuid.uuid4())}, json=maintenance_template)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "source_import_not_found"
