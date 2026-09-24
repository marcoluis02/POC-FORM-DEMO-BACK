from app.dto.form_definition import FormDefinition, FormDefinitionInput
from app.services.definition_normalizer import normalize_definition


def test_respeta_los_ids_que_ya_vienen(maintenance_template):
    result = normalize_definition(FormDefinitionInput.model_validate(maintenance_template))

    assert result.sections[0].id == "s_001"
    assert [field.id for field in result.sections[0].fields] == ["f_001", "f_002"]


def test_genera_ids_a_secciones_y_campos_nuevos(maintenance_template):
    maintenance_template["sections"][0].pop("id")
    for field in maintenance_template["sections"][0]["fields"]:
        field.pop("id")

    result = normalize_definition(FormDefinitionInput.model_validate(maintenance_template))

    assert result.sections[0].id == "s_001"
    assert [field.id for field in result.sections[0].fields] == ["f_001", "f_002"]


def test_campo_nuevo_no_reutiliza_ids_de_la_version_anterior(maintenance_template):
    previous = FormDefinition.model_validate(maintenance_template)
    # Se borra f_002 y se agrega un campo nuevo sin id
    fields = maintenance_template["sections"][0]["fields"]
    fields.pop()
    fields.append({"type": "short_text", "label": "Comentarios", "position": 2})

    result = normalize_definition(FormDefinitionInput.model_validate(maintenance_template), previous)

    assert [field.id for field in result.sections[0].fields] == ["f_001", "f_003"]


def test_ordena_por_posicion_y_deja_posiciones_consecutivas(maintenance_template):
    fields = maintenance_template["sections"][0]["fields"]
    fields[0]["position"] = 10
    fields[1]["position"] = 5

    result = normalize_definition(FormDefinitionInput.model_validate(maintenance_template))

    assert [(field.id, field.position) for field in result.sections[0].fields] == [("f_002", 1), ("f_001", 2)]
