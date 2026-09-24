import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, PayloadTooLargeError, ValidationError
from app.dto.form_definition import FormDefinitionInput
from app.dto.responses import ResponseCreateIn, ResponseValuesIn
from tests.conftest import PDF_BYTES, PNG_BYTES, TEST_MAX_PHOTOS_PER_FIELD, TEST_MAX_UPLOAD_BYTES

COMPLETE_VALUES = {"f_001": "yes", "f_002": 70, "f_003": True, "f_004": "Juan Perez"}
DEFAULT_NAME = "Visita de prueba"


@pytest.fixture
async def template(template_service, inspection_template):
    return await template_service.create_template(FormDefinitionInput.model_validate(inspection_template), None)


@pytest.fixture
async def draft(response_service, template):
    return await response_service.create_response(
        ResponseCreateIn(template_id=template.id, name=DEFAULT_NAME), None
    )


def _values(values: dict, name: str = DEFAULT_NAME) -> ResponseValuesIn:
    return ResponseValuesIn(name=name, values=values)


async def _add_photo(service, response_id, field_id="f_007", key=None, content=PNG_BYTES):
    return await service.add_attachment(response_id, field_id, "equipo.png", content, key)


# ---------- Crear y consultar ----------


async def test_crea_borrador_con_la_ultima_version(response_service, template_service, template, inspection_template):
    await template_service.create_version(template.id, FormDefinitionInput.model_validate(inspection_template), None)

    created = await response_service.create_response(
        ResponseCreateIn(template_id=template.id, name=DEFAULT_NAME), None
    )

    assert created.status == "draft"
    assert created.name == DEFAULT_NAME
    assert created.version == 2
    assert created.values == {}
    assert created.submitted_at is None


async def test_crear_con_plantilla_inexistente_da_404(response_service):
    with pytest.raises(NotFoundError):
        await response_service.create_response(ResponseCreateIn(template_id=uuid.uuid4(), name=DEFAULT_NAME), None)


async def test_crear_con_la_misma_llave_no_duplica(response_service, template, fake_db):
    data = ResponseCreateIn(template_id=template.id, name=DEFAULT_NAME)

    first = await response_service.create_response(data, "crear-1")
    second = await response_service.create_response(data, "crear-1")

    assert first.id == second.id
    assert len(fake_db.responses) == 1


async def test_consulta_respuesta_inexistente_da_404(response_service):
    with pytest.raises(NotFoundError):
        await response_service.get_response(uuid.uuid4())


# ---------- Borrador ----------


async def test_el_borrador_guarda_nombre_y_respuestas(response_service, draft):
    await response_service.save_draft(
        draft.id, _values({"f_001": "no", "f_004": "Ana"}, name="Visita Ana"), None
    )

    loaded = await response_service.get_response(draft.id)

    assert loaded.name == "Visita Ana"
    assert loaded.values == {"f_001": "no", "f_004": "Ana"}
    assert loaded.status == "draft"


async def test_el_borrador_no_exige_obligatorias_pero_si_revisa_tipos(response_service, draft, fake_db):
    with pytest.raises(ValidationError) as error:
        await response_service.save_draft(draft.id, _values({"f_002": "caliente"}), None)

    assert error.value.code == "invalid_answers"
    assert error.value.details[0].field_id == "f_002"
    assert fake_db.responses[draft.id].values_json == {}


async def test_guardar_borrador_con_la_misma_llave_y_otros_datos_da_409(response_service, draft):
    await response_service.save_draft(draft.id, _values({"f_001": "yes"}), "borrador-1")

    with pytest.raises(ConflictError) as error:
        await response_service.save_draft(draft.id, _values({"f_001": "no"}), "borrador-1")

    assert error.value.code == "idempotency_key_reused"


# ---------- Envío ----------


async def test_enviar_incompleto_da_422_con_las_preguntas_faltantes(response_service, draft, fake_db):
    with pytest.raises(ValidationError) as error:
        await response_service.submit(draft.id, _values({"f_001": "yes"}), None)

    assert error.value.code == "response_incomplete"
    assert [item.field_id for item in error.value.details] == ["f_003", "f_004", "f_007"]
    assert fake_db.responses[draft.id].status == "draft"


async def test_enviar_completo_queda_enviado(response_service, draft):
    await _add_photo(response_service, draft.id)

    submitted = await response_service.submit(draft.id, _values(COMPLETE_VALUES), None)

    assert submitted.status == "submitted"
    assert submitted.submitted_at is not None
    assert submitted.submitted_at.tzinfo is not None
    assert submitted.values == COMPLETE_VALUES
    assert len(submitted.attachments) == 1


async def test_enviado_ya_no_se_puede_cambiar(response_service, draft):
    await _add_photo(response_service, draft.id)
    await response_service.submit(draft.id, _values(COMPLETE_VALUES), None)

    with pytest.raises(ConflictError) as save_error:
        await response_service.save_draft(draft.id, _values({"f_001": "no"}), None)
    with pytest.raises(ConflictError):
        await response_service.submit(draft.id, _values(COMPLETE_VALUES), None)
    with pytest.raises(ConflictError):
        await _add_photo(response_service, draft.id)

    assert save_error.value.code == "response_already_submitted"


async def test_reintentar_el_envio_con_la_misma_llave_regresa_lo_mismo(response_service, draft):
    await _add_photo(response_service, draft.id)

    first = await response_service.submit(draft.id, _values(COMPLETE_VALUES), "enviar-1")
    second = await response_service.submit(draft.id, _values(COMPLETE_VALUES), "enviar-1")

    assert first.submitted_at == second.submitted_at
    assert second.status == "submitted"


# ---------- Fotos ----------


async def test_sube_foto_a_una_pregunta_de_foto(response_service, draft, fake_storage, fake_db):
    photo = await _add_photo(response_service, draft.id)

    stored = fake_db.attachments[photo.id]
    assert photo.field_id == "f_007"
    assert photo.mime_type == "image/png"
    assert photo.url.startswith(f"https://storage.test/responses/{draft.id}/")
    assert stored.file_key in fake_storage.objects


async def test_acepta_evidencia_en_preguntas_con_evidencia(response_service, draft):
    photo = await _add_photo(response_service, draft.id, field_id="f_001")

    assert photo.field_id == "f_001"


async def test_rechaza_fotos_en_preguntas_sin_fotos(response_service, draft, fake_storage):
    with pytest.raises(ValidationError) as error:
        await _add_photo(response_service, draft.id, field_id="f_002")

    assert error.value.code == "field_without_photos"
    assert fake_storage.put_calls == 0


async def test_rechaza_pregunta_inexistente(response_service, draft):
    with pytest.raises(ValidationError) as error:
        await _add_photo(response_service, draft.id, field_id="f_999")

    assert error.value.code == "unknown_field"


async def test_rechaza_pdf_y_archivos_que_no_son_foto(response_service, draft, fake_storage):
    with pytest.raises(ValidationError) as pdf_error:
        await _add_photo(response_service, draft.id, content=PDF_BYTES)
    with pytest.raises(ValidationError):
        await _add_photo(response_service, draft.id, content=b"no soy una foto")

    assert pdf_error.value.code == "unsupported_file_type"
    assert fake_storage.put_calls == 0


async def test_rechaza_foto_muy_pesada(response_service, draft):
    with pytest.raises(PayloadTooLargeError):
        await _add_photo(response_service, draft.id, content=PNG_BYTES + b"\x00" * TEST_MAX_UPLOAD_BYTES)


async def test_no_deja_pasar_del_maximo_de_fotos(response_service, draft):
    for _ in range(TEST_MAX_PHOTOS_PER_FIELD):
        await _add_photo(response_service, draft.id)

    with pytest.raises(ValidationError) as error:
        await _add_photo(response_service, draft.id)

    assert error.value.code == "too_many_photos"


async def test_reintentar_la_subida_con_la_misma_llave_no_duplica(response_service, draft, fake_storage, fake_db):
    first = await _add_photo(response_service, draft.id, key="foto-1")
    second = await _add_photo(response_service, draft.id, key="foto-1")

    assert first.id == second.id
    assert len(fake_db.attachments) == 1
    assert len(fake_storage.objects) == 1


async def test_si_el_registro_falla_se_borra_el_archivo_de_s3(response_service, draft, fake_storage, fake_db):
    await _add_photo(response_service, draft.id, key="foto-1")
    keys_antes = set(fake_storage.objects)

    # Misma llave con otra pregunta: el archivo nuevo ya subió pero no se registra
    with pytest.raises(ConflictError):
        await _add_photo(response_service, draft.id, field_id="f_001", key="foto-1")

    # El put fallido se borró al momento; solo queda la foto que sí se registró
    assert set(fake_storage.objects) == keys_antes
    assert fake_db.pending_deletes() == []

async def test_quitar_foto_la_borra_y_programa_borrar_el_archivo(response_service, draft, fake_db):
    photo = await _add_photo(response_service, draft.id)
    file_key = fake_db.attachments[photo.id].file_key

    deleted = await response_service.delete_attachment(draft.id, photo.id, "quitar-1")
    again = await response_service.delete_attachment(draft.id, photo.id, "quitar-1")

    assert deleted.id == again.id == photo.id
    assert photo.id not in fake_db.attachments
    assert fake_db.pending_deletes() == [file_key]


async def test_quitar_foto_inexistente_da_404(response_service, draft):
    with pytest.raises(NotFoundError):
        await response_service.delete_attachment(draft.id, uuid.uuid4(), None)


# ---------- Listado ----------


async def test_lista_por_plantilla_del_mas_nuevo_al_mas_viejo_con_cursor(response_service, template):
    created = [
        await response_service.create_response(ResponseCreateIn(template_id=template.id, name=f"Llenado {i}"), None)
        for i in range(3)
    ]

    first_page = await response_service.list_responses(template.id, 2, None)
    second_page = await response_service.list_responses(template.id, 2, first_page.next_cursor)

    listed = [item.id for item in first_page.items + second_page.items]
    assert sorted(listed) == sorted(item.id for item in created)
    assert len(first_page.items) == 2
    assert first_page.next_cursor is not None
    assert second_page.next_cursor is None
    assert first_page.items[0].status == "draft"


async def test_listado_de_plantilla_inexistente_da_404(response_service):
    with pytest.raises(NotFoundError):
        await response_service.list_responses(uuid.uuid4(), 10, None)


async def test_listado_con_cursor_invalido_da_422(response_service, template):
    with pytest.raises(ValidationError) as error:
        await response_service.list_responses(template.id, 10, "cursor-roto")

    assert error.value.code == "invalid_cursor"
