import uuid

import pytest

from app.core.config import get_settings
from app.factories.services_factory import get_response_service, get_template_service
from app.main import app
from tests.conftest import PDF_BYTES, PNG_BYTES

RESPONSES_URL = f"{get_settings().api_prefix}/responses"
TEMPLATES_URL = f"{get_settings().api_prefix}/templates"
DEFAULT_NAME = "Visita de prueba"
COMPLETE_BODY = {"name": DEFAULT_NAME, "values": {"f_001": "yes", "f_003": True, "f_004": "Juan Perez"}}


@pytest.fixture(autouse=True)
def use_fake_services(response_service, template_service):
    app.dependency_overrides[get_response_service] = lambda: response_service
    app.dependency_overrides[get_template_service] = lambda: template_service


@pytest.fixture
async def template_id(client, inspection_template) -> str:
    return (await client.post(TEMPLATES_URL, json=inspection_template)).json()["id"]


@pytest.fixture
async def response_id(client, template_id) -> str:
    created = await client.post(RESPONSES_URL, json={"template_id": template_id, "name": DEFAULT_NAME})
    return created.json()["id"]


async def _upload(client, response_id, field_id="f_007", content=PNG_BYTES):
    return await client.post(
        f"{RESPONSES_URL}/{response_id}/attachments",
        data={"field_id": field_id},
        files={"file": ("equipo.png", content, "image/png")},
    )


async def test_flujo_completo_borrador_recarga_y_envio(client, template_id):
    created = await client.post(RESPONSES_URL, json={"template_id": template_id, "name": "Llenado 1"})
    response_id = created.json()["id"]

    saved = await client.put(
        f"{RESPONSES_URL}/{response_id}",
        json={"name": "Llenado 1 corregido", "values": {"f_001": "yes", "f_004": "Juan"}},
    )
    reloaded = await client.get(f"{RESPONSES_URL}/{response_id}")
    incomplete = await client.post(
        f"{RESPONSES_URL}/{response_id}/submit", json={"name": "Llenado 1 corregido", "values": {"f_001": "yes"}}
    )
    photo = await _upload(client, response_id)
    submitted = await client.post(
        f"{RESPONSES_URL}/{response_id}/submit",
        json={"name": "Llenado 1 corregido", "values": COMPLETE_BODY["values"]},
    )

    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert created.json()["name"] == "Llenado 1"
    assert saved.status_code == 200
    assert reloaded.json()["name"] == "Llenado 1 corregido"
    assert reloaded.json()["values"] == {"f_001": "yes", "f_004": "Juan"}
    assert incomplete.status_code == 422
    assert incomplete.json()["error"]["code"] == "response_incomplete"
    assert {item["field_id"] for item in incomplete.json()["error"]["details"]} == {"f_003", "f_004", "f_007"}
    assert photo.status_code == 201
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["name"] == "Llenado 1 corregido"
    assert submitted.json()["submitted_at"] is not None


async def test_sin_nombre_al_crear_da_422(client, template_id):
    response = await client.post(RESPONSES_URL, json={"template_id": template_id})

    assert response.status_code == 422


async def test_valores_invalidos_dan_422_con_la_pregunta(client, response_id):
    response = await client.put(
        f"{RESPONSES_URL}/{response_id}", json={"name": DEFAULT_NAME, "values": {"f_002": "caliente"}}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_answers"
    assert response.json()["error"]["details"][0]["field_id"] == "f_002"


async def test_cambiar_un_formulario_enviado_da_409(client, response_id):
    await _upload(client, response_id)
    await client.post(f"{RESPONSES_URL}/{response_id}/submit", json=COMPLETE_BODY)

    response = await client.put(f"{RESPONSES_URL}/{response_id}", json={"name": DEFAULT_NAME, "values": {}})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "response_already_submitted"


async def test_la_foto_sale_con_url_y_sin_la_key_de_s3(client, response_id):
    photo = await _upload(client, response_id)
    detail = await client.get(f"{RESPONSES_URL}/{response_id}")

    assert photo.json()["url"].startswith("https://storage.test/")
    assert "file_key" not in photo.json()
    assert detail.json()["attachments"][0]["id"] == photo.json()["id"]


async def test_pdf_como_foto_da_422(client, response_id):
    response = await _upload(client, response_id, content=PDF_BYTES)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_file_type"


async def test_field_id_con_formato_invalido_da_422(client, response_id):
    response = await _upload(client, response_id, field_id="foto")

    assert response.status_code == 422


async def test_quitar_foto(client, response_id):
    photo = (await _upload(client, response_id)).json()

    deleted = await client.delete(f"{RESPONSES_URL}/{response_id}/attachments/{photo['id']}")
    detail = await client.get(f"{RESPONSES_URL}/{response_id}")

    assert deleted.status_code == 200
    assert deleted.json() == {"id": photo["id"]}
    assert detail.json()["attachments"] == []


async def test_listado_paginado_por_plantilla(client, template_id):
    for index in range(3):
        await client.post(RESPONSES_URL, json={"template_id": template_id, "name": f"Llenado {index}"})

    first = await client.get(RESPONSES_URL, params={"template_id": template_id, "limit": 2})
    second = await client.get(
        RESPONSES_URL, params={"template_id": template_id, "limit": 2, "cursor": first.json()["next_cursor"]}
    )

    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert "name" in first.json()["items"][0]
    assert len(second.json()["items"]) == 1
    assert second.json()["next_cursor"] is None


async def test_listado_sin_plantilla_o_con_limite_excedido_da_422(client, template_id):
    without_template = await client.get(RESPONSES_URL)
    too_big = await client.get(
        RESPONSES_URL, params={"template_id": template_id, "limit": get_settings().pagination_max_limit + 1}
    )

    assert without_template.status_code == 422
    assert too_big.status_code == 422


async def test_respuesta_inexistente_da_404(client):
    response = await client.get(f"{RESPONSES_URL}/{uuid.uuid4()}")

    assert response.status_code == 404
