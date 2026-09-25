import copy
import uuid

import pytest

from app.core.config import get_settings
from app.domain.import_status import ImportStatus
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


async def test_el_tipo_que_dice_el_navegador_no_cuenta(client):
    # Imagen PNG disfrazada de PDF: se guarda como lo que realmente es
    disguised = await client.post(IMPORTS_URL, files={"file": ("doc.pdf", PNG_BYTES, "application/pdf")})
    # Texto disfrazado de imagen: se rechaza
    fake_image = await client.post(IMPORTS_URL, files={"file": ("foto.png", b"no soy una foto", "image/png")})

    assert disguised.status_code == 201
    assert disguised.json()["mime_type"] == "image/png"
    assert fake_image.status_code == 422
    assert fake_image.json()["error"]["code"] == "unsupported_file_type"


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
    body = response.json()
    assert body["id"] == created["id"]
    assert body["status"] == "received"
    assert body["warnings"] == []
    assert body["draft_json"] is None
    assert body["error_code"] is None
    assert body["error_message"] is None
    assert "original_file_key" not in body
    assert "original_url" in body


async def test_el_get_incluye_draft_warnings_y_error_si_existen(import_service, fake_db, client):
    created = (await client.post(IMPORTS_URL, files={"file": ("r.png", PNG_BYTES, "image/png")})).json()
    entity = fake_db.imports[uuid.UUID(created["id"])]
    entity.status = "requires_review"
    entity.draft_json = {"schema_version": 1, "title": "Borrador IA", "sections": []}
    entity.warnings = [{"code": "low_confidence", "message": "Revisa esta pregunta"}]
    entity.error_code = None
    entity.error_message = None
    entity.page_count = 1
    entity.detected_fields_count = 3

    response = await client.get(f"{IMPORTS_URL}/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "requires_review"
    assert body["draft_json"]["title"] == "Borrador IA"
    assert body["warnings"][0]["code"] == "low_confidence"
    assert body["page_count"] == 1
    assert body["detected_fields_count"] == 3
    assert body["error_code"] is None


async def test_consulta_de_documento_inexistente_da_404(client):
    response = await client.get(f"{IMPORTS_URL}/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_la_plantilla_queda_ligada_al_documento(client, maintenance_template, fake_db):
    document = (await client.post(IMPORTS_URL, files={"file": ("r.png", PNG_BYTES, "image/png")})).json()
    entity = fake_db.imports[uuid.UUID(document["id"])]
    entity.status = ImportStatus.REQUIRES_REVIEW
    entity.draft_json = copy.deepcopy(maintenance_template)
    entity.corrections_count = 0

    response = await client.post(TEMPLATES_URL, params={"source_import_id": document["id"]}, json=maintenance_template)

    assert response.status_code == 201
    assert response.json()["current_version"]["source_import_id"] == document["id"]


async def test_no_crea_plantilla_desde_import_que_aun_no_esta_listo(client, maintenance_template):
    document = (await client.post(IMPORTS_URL, files={"file": ("r.png", PNG_BYTES, "image/png")})).json()

    response = await client.post(TEMPLATES_URL, params={"source_import_id": document["id"]}, json=maintenance_template)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "source_import_not_ready"


async def test_confirmar_draft_actualiza_corrections_count_por_api(client, maintenance_template, fake_db):
    document = (await client.post(IMPORTS_URL, files={"file": ("r.png", PNG_BYTES, "image/png")})).json()
    entity = fake_db.imports[uuid.UUID(document["id"])]
    entity.status = ImportStatus.REQUIRES_REVIEW
    entity.draft_json = copy.deepcopy(maintenance_template)
    entity.corrections_count = 0

    revised = copy.deepcopy(maintenance_template)
    revised["sections"][0]["fields"][0]["label"] = "¿El filtro quedó completamente limpio?"

    created = await client.post(TEMPLATES_URL, params={"source_import_id": document["id"]}, json=revised)
    refreshed = await client.get(f"{IMPORTS_URL}/{document['id']}")

    assert created.status_code == 201
    assert refreshed.status_code == 200
    assert refreshed.json()["corrections_count"] == 1


async def test_plantilla_con_documento_inexistente_da_422(client, maintenance_template):
    response = await client.post(TEMPLATES_URL, params={"source_import_id": str(uuid.uuid4())}, json=maintenance_template)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "source_import_not_found"
