import uuid

import pytest

from app.core.config import get_settings
from app.factories.services_factory import get_template_service
from app.main import app

TEMPLATES_URL = f"{get_settings().api_prefix}/templates"


@pytest.fixture(autouse=True)
def use_fake_service(template_service):
    app.dependency_overrides[get_template_service] = lambda: template_service


async def test_post_crea_la_plantilla_v1(client, maintenance_template):
    response = await client.post(TEMPLATES_URL, json=maintenance_template)

    assert response.status_code == 201
    body = response.json()
    assert body["latest_version"] == 1
    assert body["status"] == "active"
    assert body["current_version"]["definition"]["sections"][0]["fields"][1]["unit"] == "°F"


async def test_listado_regresa_resumen_sin_definicion(client, maintenance_template):
    await client.post(TEMPLATES_URL, json=maintenance_template)

    response = await client.get(TEMPLATES_URL)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Revisión de mantenimiento"
    assert "current_version" not in body["items"][0]
    assert body["next_cursor"] is None


async def test_listado_rechaza_limite_mayor_al_maximo(client):
    response = await client.get(TEMPLATES_URL, params={"limit": get_settings().pagination_max_limit + 1})

    assert response.status_code == 422


async def test_listado_con_cursor_invalido_da_422(client):
    response = await client.get(TEMPLATES_URL, params={"cursor": "basura"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cursor"


async def test_get_regresa_la_plantilla_creada(client, maintenance_template):
    created = (await client.post(TEMPLATES_URL, json=maintenance_template)).json()

    response = await client.get(f"{TEMPLATES_URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json()["current_version"]["id"] == created["current_version"]["id"]


async def test_get_version_especifica(client, maintenance_template):
    created = (await client.post(TEMPLATES_URL, json=maintenance_template)).json()

    response = await client.get(f"{TEMPLATES_URL}/{created['id']}/versions/1")

    assert response.status_code == 200
    assert response.json()["version"] == 1


async def test_post_version_crea_la_v2(client, maintenance_template):
    created = (await client.post(TEMPLATES_URL, json=maintenance_template)).json()
    maintenance_template["title"] = "Revisión v2"

    response = await client.post(f"{TEMPLATES_URL}/{created['id']}/versions", json=maintenance_template)

    assert response.status_code == 201
    assert response.json()["latest_version"] == 2


async def test_plantilla_inexistente_da_404_estandar(client):
    response = await client.get(f"{TEMPLATES_URL}/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_definicion_invalida_da_422_con_el_campo(client, maintenance_template):
    maintenance_template["sections"][0]["fields"][0]["type"] = "firma"

    response = await client.post(TEMPLATES_URL, json=maintenance_template)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_idempotency_key_regresa_la_misma_plantilla(client, maintenance_template, fake_db):
    headers = {"Idempotency-Key": "demo-123"}

    first = await client.post(TEMPLATES_URL, json=maintenance_template, headers=headers)
    second = await client.post(TEMPLATES_URL, json=maintenance_template, headers=headers)

    assert first.json()["id"] == second.json()["id"]
    assert len(fake_db.templates) == 1


async def test_idempotency_key_con_otros_datos_da_409(client, maintenance_template):
    headers = {"Idempotency-Key": "demo-123"}
    await client.post(TEMPLATES_URL, json=maintenance_template, headers=headers)
    maintenance_template["title"] = "Otro"

    response = await client.post(TEMPLATES_URL, json=maintenance_template, headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_key_reused"
