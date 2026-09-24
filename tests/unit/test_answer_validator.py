import pytest

from app.domain.answer_rules import LONG_TEXT_MAX_LENGTH, NUMBER_MAX_ABS, SHORT_TEXT_MAX_LENGTH
from app.dto.form_definition import FormDefinition
from app.services.answer_validator import clean_values, missing_required


@pytest.fixture
def definition(inspection_template) -> FormDefinition:
    return FormDefinition.model_validate(inspection_template)


def _errors(definition, values) -> dict[str, str]:
    _, errors = clean_values(definition, values)
    return {error.field_id: error.code for error in errors}


def test_acepta_respuestas_validas_de_cada_tipo(definition):
    values = {
        "f_001": "yes",
        "f_002": 72.5,
        "f_003": True,
        "f_004": "  Juan Perez  ",
        "f_005": "Todo bien",
        "f_006": "2026-09-24",
    }

    cleaned, errors = clean_values(definition, values)

    assert errors == []
    assert cleaned == {**values, "f_004": "Juan Perez"}


def test_select_solo_acepta_valores_de_sus_opciones():
    definition = FormDefinition.model_validate(
        {
            "schema_version": 1,
            "title": "Lista",
            "sections": [
                {
                    "id": "s_001",
                    "title": "General",
                    "position": 1,
                    "fields": [
                        {
                            "id": "f_010",
                            "type": "select",
                            "label": "Estado",
                            "required": True,
                            "position": 1,
                            "allow_evidence": False,
                            "options": [
                                {"value": "ok", "label": "Bien"},
                                {"value": "fail", "label": "Mal"},
                            ],
                        }
                    ],
                }
            ],
        }
    )

    cleaned, errors = clean_values(definition, {"f_010": "ok"})
    assert errors == []
    assert cleaned == {"f_010": "ok"}

    assert _errors(definition, {"f_010": "tal vez"}) == {"f_010": "invalid_value"}


def test_null_y_texto_vacio_cuentan_como_sin_contestar(definition):
    cleaned, errors = clean_values(definition, {"f_001": None, "f_004": "   ", "f_002": 0})

    assert errors == []
    assert cleaned == {"f_002": 0}


@pytest.mark.parametrize(
    ("field_id", "value"),
    [
        ("f_001", "tal vez"),
        ("f_001", True),
        ("f_002", "72"),
        ("f_002", True),
        ("f_002", NUMBER_MAX_ABS + 1),
        ("f_002", float("inf")),
        ("f_003", "si"),
        ("f_003", 1),
        ("f_004", 123),
        ("f_004", "a" * (SHORT_TEXT_MAX_LENGTH + 1)),
        ("f_005", "a" * (LONG_TEXT_MAX_LENGTH + 1)),
        ("f_006", "24/09/2026"),
        ("f_006", "2026-02-30"),
        ("f_007", "foto.png"),
        ("f_008", "firma"),
    ],
)
def test_rechaza_valores_que_no_corresponden_al_tipo(definition, field_id, value):
    assert _errors(definition, {field_id: value}) == {field_id: "invalid_value"}


def test_rechaza_preguntas_que_no_existen(definition):
    assert _errors(definition, {"f_999": "yes"}) == {"f_999": "unknown_field"}


def test_marca_todas_las_obligatorias_que_faltan(definition):
    missing = missing_required(definition, {}, set())

    # La firma nunca se exige: queda como "próximamente"
    assert [item.field_id for item in missing] == ["f_001", "f_003", "f_004", "f_007"]
    assert {item.code for item in missing} == {"required"}


def test_casilla_obligatoria_desmarcada_cuenta_como_faltante(definition):
    values = {"f_001": "na", "f_003": False, "f_004": "Ana"}

    missing = missing_required(definition, values, {"f_007"})

    assert [item.field_id for item in missing] == ["f_003"]


def test_foto_obligatoria_se_cumple_con_una_foto_subida(definition):
    values = {"f_001": "no", "f_003": True, "f_004": "Ana"}

    assert missing_required(definition, values, {"f_007"}) == []
    assert [item.field_id for item in missing_required(definition, values, set())] == ["f_007"]
