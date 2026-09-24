import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.dto.form_definition import FormDefinitionInput
from tests.conftest import PNG_BYTES


def _input(data: dict) -> FormDefinitionInput:
    return FormDefinitionInput.model_validate(data)


async def test_crear_plantilla_crea_version_1(template_service, maintenance_template, fake_db):
    created = await template_service.create_template(_input(maintenance_template), None)

    assert created.latest_version == 1
    assert created.name == "Revisión de mantenimiento"
    assert created.current_version.version == 1
    assert created.current_version.definition.sections[0].fields[0].id == "f_001"
    assert len(fake_db.templates) == 1
    assert len(fake_db.versions) == 1


async def test_al_confirmar_se_guardan_posiciones_consecutivas(template_service, maintenance_template, fake_db):
    maintenance_template["sections"][0]["position"] = 7
    maintenance_template["sections"][0]["fields"][0]["position"] = 3
    maintenance_template["sections"][0]["fields"][1]["position"] = 9

    created = await template_service.create_template(_input(maintenance_template), None)

    stored = next(iter(fake_db.versions.values())).definition_json
    assert stored["sections"][0]["position"] == 1
    assert [field["position"] for field in stored["sections"][0]["fields"]] == [1, 2]
    assert created.current_version.definition.sections[0].position == 1


async def test_consultar_plantilla_regresa_la_ultima_version(template_service, maintenance_template):
    created = await template_service.create_template(_input(maintenance_template), None)

    found = await template_service.get_template(created.id)

    assert found.id == created.id
    assert found.current_version.definition.title == "Revisión de mantenimiento"


async def test_plantilla_inexistente_da_not_found(template_service):
    with pytest.raises(NotFoundError):
        await template_service.get_template(uuid.uuid4())


async def test_nueva_version_incrementa_y_no_toca_la_anterior(template_service, maintenance_template):
    created = await template_service.create_template(_input(maintenance_template), None)
    maintenance_template["title"] = "Revisión v2"
    maintenance_template["sections"][0]["fields"].append({"type": "short_text", "label": "Notas", "position": 3})

    updated = await template_service.create_version(created.id, _input(maintenance_template), None)
    first = await template_service.get_version(created.id, 1)

    assert updated.latest_version == 2
    assert updated.name == "Revisión v2"
    assert updated.current_version.definition.sections[0].fields[2].id == "f_003"
    assert first.definition.title == "Revisión de mantenimiento"
    assert len(first.definition.sections[0].fields) == 2


async def test_version_de_plantilla_inexistente_da_not_found(template_service, maintenance_template):
    with pytest.raises(NotFoundError):
        await template_service.create_version(uuid.uuid4(), _input(maintenance_template), None)


async def test_version_inexistente_da_not_found(template_service, maintenance_template):
    created = await template_service.create_template(_input(maintenance_template), None)

    with pytest.raises(NotFoundError):
        await template_service.get_version(created.id, 99)


async def test_reintento_con_misma_clave_no_duplica(template_service, maintenance_template, fake_db):
    first = await template_service.create_template(_input(maintenance_template), "clave-1")
    second = await template_service.create_template(_input(maintenance_template), "clave-1")

    assert second.id == first.id
    assert len(fake_db.templates) == 1


async def test_misma_clave_con_otros_datos_da_conflicto(template_service, maintenance_template):
    await template_service.create_template(_input(maintenance_template), "clave-1")
    maintenance_template["title"] = "Otro título"

    with pytest.raises(ConflictError) as error:
        await template_service.create_template(_input(maintenance_template), "clave-1")

    assert error.value.code == "idempotency_key_reused"


async def test_listado_pagina_de_la_mas_nueva_a_la_mas_vieja(template_service, maintenance_template):
    created = []
    for number in range(5):
        maintenance_template["title"] = f"Plantilla {number}"
        created.append(await template_service.create_template(_input(maintenance_template), None))
    # Mismo orden que la consulta: fecha y, si empatan, id
    newest_first = [t.id for t in sorted(created, key=lambda t: (t.created_at, t.id), reverse=True)]

    first_page = await template_service.list_templates(2, None)
    second_page = await template_service.list_templates(2, first_page.next_cursor)
    last_page = await template_service.list_templates(2, second_page.next_cursor)

    listed = [item.id for page in (first_page, second_page, last_page) for item in page.items]
    assert listed == newest_first
    assert last_page.next_cursor is None


async def test_listado_vacio(template_service):
    page = await template_service.list_templates(20, None)

    assert page.items == []
    assert page.next_cursor is None


async def test_listado_con_cursor_invalido_da_error(template_service):
    with pytest.raises(ValidationError) as error:
        await template_service.list_templates(20, "no-es-un-cursor")

    assert error.value.code == "invalid_cursor"


async def test_claves_distintas_crean_plantillas_distintas(template_service, maintenance_template, fake_db):
    await template_service.create_template(_input(maintenance_template), "clave-1")
    await template_service.create_template(_input(maintenance_template), "clave-2")

    assert len(fake_db.templates) == 2


async def test_crear_plantilla_con_documento_original(template_service, import_service, maintenance_template):
    document = await import_service.create_import("revision.png", PNG_BYTES, None)

    created = await template_service.create_template(_input(maintenance_template), None, document.id)

    assert created.current_version.source_import_id == document.id


async def test_documento_original_inexistente_da_error(template_service, maintenance_template, fake_db):
    with pytest.raises(ValidationError) as error:
        await template_service.create_template(_input(maintenance_template), None, uuid.uuid4())

    assert error.value.code == "source_import_not_found"
    assert fake_db.templates == {}


async def test_nueva_version_reemplaza_el_documento_solo_si_llega_uno(
    template_service, import_service, maintenance_template
):
    first = await import_service.create_import("v1.png", PNG_BYTES, None)
    created = await template_service.create_template(_input(maintenance_template), None, first.id)

    kept = await template_service.create_version(created.id, _input(maintenance_template), None)
    assert kept.current_version.source_import_id == first.id

    second = await import_service.create_import("v2.png", PNG_BYTES + b"\x01", None)
    replaced = await template_service.create_version(created.id, _input(maintenance_template), None, second.id)
    assert replaced.current_version.source_import_id == second.id


async def test_el_documento_nuevo_no_cambia_las_versiones_anteriores(
    template_service, import_service, maintenance_template
):
    created = await template_service.create_template(_input(maintenance_template), None)
    document = await import_service.create_import("v2.png", PNG_BYTES, None)

    await template_service.create_version(created.id, _input(maintenance_template), None, document.id)

    assert (await template_service.get_version(created.id, 1)).source_import_id is None
    assert (await template_service.get_version(created.id, 2)).source_import_id == document.id
