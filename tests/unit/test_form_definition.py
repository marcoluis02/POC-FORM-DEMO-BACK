import pytest
from pydantic import ValidationError

from app.domain.field_types import FieldType
from app.dto.form_definition import FormDefinition, FormDefinitionInput


def test_fixture_acordado_es_valido(maintenance_template):
    definition = FormDefinition.model_validate(maintenance_template)

    fields = definition.sections[0].fields
    assert definition.title == "Revisión de mantenimiento"
    assert fields[0].type == FieldType.YES_NO_NA
    assert fields[0].required is True
    assert fields[0].allow_evidence is True
    assert fields[1].unit == "°F"


def test_acepta_todos_los_tipos_soportados(maintenance_template):
    base_field = maintenance_template["sections"][0]["fields"][0]
    sample_options = [
        {"value": "a", "label": "Opción A"},
        {"value": "b", "label": "Opción B"},
    ]
    maintenance_template["sections"][0]["fields"] = [
        {
            **base_field,
            "id": f"f_{index:03d}",
            "type": field_type.value,
            "position": index,
            "unit": None,
            "options": sample_options if field_type == FieldType.SELECT else None,
        }
        for index, field_type in enumerate(FieldType, start=1)
    ]

    definition = FormDefinition.model_validate(maintenance_template)

    assert {f.type for f in definition.sections[0].fields} == set(FieldType)


def test_select_exige_opciones_con_valores_unicos(maintenance_template):
    field = maintenance_template["sections"][0]["fields"][0]
    field["type"] = FieldType.SELECT
    field["unit"] = None
    field["options"] = [{"value": "ok", "label": "Bien"}, {"value": "ok", "label": "Otro"}]

    with pytest.raises(ValidationError, match="mismo valor"):
        FormDefinition.model_validate(maintenance_template)


def test_select_sin_opciones_se_rechaza(maintenance_template):
    field = maintenance_template["sections"][0]["fields"][0]
    field["type"] = FieldType.SELECT
    field["unit"] = None
    field.pop("options", None)

    with pytest.raises(ValidationError, match="al menos 2 opciones"):
        FormDefinition.model_validate(maintenance_template)


def test_opciones_en_campo_que_no_es_select_se_rechazan(maintenance_template):
    field = maintenance_template["sections"][0]["fields"][0]
    field["options"] = [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]

    with pytest.raises(ValidationError, match="solo aplican"):
        FormDefinition.model_validate(maintenance_template)


def test_select_valido_guarda_las_opciones(maintenance_template):
    field = maintenance_template["sections"][0]["fields"][0]
    field["type"] = FieldType.SELECT
    field["unit"] = None
    field["options"] = [
        {"value": "bueno", "label": "Bueno"},
        {"value": "regular", "label": "Regular"},
        {"value": "malo", "label": "Malo"},
    ]

    definition = FormDefinition.model_validate(maintenance_template)

    assert [option.value for option in definition.sections[0].fields[0].options] == [
        "bueno",
        "regular",
        "malo",
    ]


def test_rechaza_tipo_no_soportado(maintenance_template):
    maintenance_template["sections"][0]["fields"][0]["type"] = "dropdown"

    with pytest.raises(ValidationError):
        FormDefinition.model_validate(maintenance_template)


def test_rechaza_unidad_en_campo_que_no_es_numero(maintenance_template):
    maintenance_template["sections"][0]["fields"][0]["unit"] = "kg"

    with pytest.raises(ValidationError, match="La unidad solo aplica"):
        FormDefinition.model_validate(maintenance_template)


def test_unidad_vacia_se_guarda_como_none(maintenance_template):
    maintenance_template["sections"][0]["fields"][1]["unit"] = "   "

    definition = FormDefinition.model_validate(maintenance_template)

    assert definition.sections[0].fields[1].unit is None


def test_required_y_allow_evidence_son_false_si_no_vienen(maintenance_template):
    field = maintenance_template["sections"][0]["fields"][1]
    del field["required"]
    del field["allow_evidence"]

    definition = FormDefinition.model_validate(maintenance_template)

    assert definition.sections[0].fields[1].required is False
    assert definition.sections[0].fields[1].allow_evidence is False


def test_rechaza_ids_de_campo_repetidos(maintenance_template):
    maintenance_template["sections"][0]["fields"][1]["id"] = "f_001"

    with pytest.raises(ValidationError, match="mismo id"):
        FormDefinition.model_validate(maintenance_template)


def test_rechaza_posiciones_repetidas_en_una_seccion(maintenance_template):
    maintenance_template["sections"][0]["fields"][1]["position"] = 1

    with pytest.raises(ValidationError, match="misma posición"):
        FormDefinition.model_validate(maintenance_template)


def test_lo_que_manda_el_cliente_puede_traer_posiciones_con_saltos(maintenance_template):
    maintenance_template["sections"][0]["position"] = 7
    maintenance_template["sections"][0]["fields"][1]["position"] = 9

    FormDefinitionInput.model_validate(maintenance_template)


def test_la_definicion_confirmada_rechaza_secciones_con_saltos(maintenance_template):
    maintenance_template["sections"][0]["position"] = 7

    with pytest.raises(ValidationError, match="sin saltos"):
        FormDefinition.model_validate(maintenance_template)


def test_la_definicion_confirmada_rechaza_campos_con_saltos(maintenance_template):
    maintenance_template["sections"][0]["fields"][1]["position"] = 9

    with pytest.raises(ValidationError, match="sin saltos"):
        FormDefinition.model_validate(maintenance_template)


def test_rechaza_llaves_desconocidas(maintenance_template):
    maintenance_template["sections"][0]["fields"][0]["color"] = "rojo"

    with pytest.raises(ValidationError):
        FormDefinition.model_validate(maintenance_template)


def test_rechaza_version_de_esquema_distinta(maintenance_template):
    maintenance_template["schema_version"] = 2

    with pytest.raises(ValidationError):
        FormDefinition.model_validate(maintenance_template)


def test_rechaza_formulario_sin_secciones(maintenance_template):
    maintenance_template["sections"] = []

    with pytest.raises(ValidationError):
        FormDefinition.model_validate(maintenance_template)


def test_rechaza_etiqueta_vacia(maintenance_template):
    maintenance_template["sections"][0]["fields"][0]["label"] = "   "

    with pytest.raises(ValidationError):
        FormDefinition.model_validate(maintenance_template)


def test_input_permite_ids_vacios_pero_la_definicion_confirmada_no(maintenance_template):
    for section in maintenance_template["sections"]:
        del section["id"]
        for field in section["fields"]:
            del field["id"]

    FormDefinitionInput.model_validate(maintenance_template)
    with pytest.raises(ValidationError):
        FormDefinition.model_validate(maintenance_template)
