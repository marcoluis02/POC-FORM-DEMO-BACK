import math
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.core.exceptions import ErrorDetail
from app.domain.answer_rules import (
    DATE_FORMAT,
    LONG_TEXT_MAX_LENGTH,
    NO_VALUE_FIELD_TYPES,
    NOT_REQUIRED_ON_SUBMIT,
    NUMBER_MAX_ABS,
    SHORT_TEXT_MAX_LENGTH,
    YesNoNa,
)
from app.domain.field_types import FieldType
from app.dto.form_definition import FieldDefinition, FormDefinition

REQUIRED_MESSAGE = "Esta pregunta es obligatoria."
UNKNOWN_FIELD_MESSAGE = "Esta pregunta no existe en el formulario."
NO_VALUE_MESSAGE = "Esta pregunta no se contesta con texto."


class InvalidAnswer(Exception):
    pass


def _clean_checkbox(value: Any) -> bool:
    if not isinstance(value, bool):
        raise InvalidAnswer("Marca o desmarca la casilla.")
    return value


def _clean_yes_no_na(value: Any) -> str:
    if not isinstance(value, str) or value not in {option.value for option in YesNoNa}:
        raise InvalidAnswer("Elige Sí, No o No aplica.")
    return value


def _text_cleaner(max_length: int) -> Callable[[Any], str | None]:
    def clean(value: Any) -> str | None:
        if not isinstance(value, str):
            raise InvalidAnswer("La respuesta debe ser texto.")
        text = value.strip()
        if len(text) > max_length:
            raise InvalidAnswer(f"La respuesta no puede pasar de {max_length} caracteres.")
        return text or None

    return clean


def _clean_number(value: Any) -> int | float:
    # bool es subclase de int en Python: se descarta a propósito
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidAnswer("Escribe solo números.")
    if not math.isfinite(value) or abs(value) > NUMBER_MAX_ABS:
        raise InvalidAnswer("El número es demasiado grande.")
    return value


def _clean_date(value: Any) -> str:
    if not isinstance(value, str):
        raise InvalidAnswer("Elige una fecha válida.")
    try:
        datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        raise InvalidAnswer("Elige una fecha válida.") from None
    return value


def _clean_select(value: Any, field: FieldDefinition) -> str:
    allowed = {option.value for option in field.options or []}
    if not isinstance(value, str) or value not in allowed:
        raise InvalidAnswer("Elige una de las opciones de la lista.")
    return value


CLEANERS: dict[FieldType, Callable[[Any], Any]] = {
    FieldType.CHECKBOX: _clean_checkbox,
    FieldType.YES_NO_NA: _clean_yes_no_na,
    FieldType.SHORT_TEXT: _text_cleaner(SHORT_TEXT_MAX_LENGTH),
    FieldType.LONG_TEXT: _text_cleaner(LONG_TEXT_MAX_LENGTH),
    FieldType.NUMBER: _clean_number,
    FieldType.DATE: _clean_date,
}


def fields_by_id(definition: FormDefinition) -> dict[str, FieldDefinition]:
    return {field.id: field for section in definition.sections for field in section.fields}


def clean_values(definition: FormDefinition, values: dict[str, Any]) -> tuple[dict[str, Any], list[ErrorDetail]]:
    """Revisa cada respuesta contra el tipo de su pregunta.
    Regresa solo las contestadas (null y texto vacío se quitan) y la lista de errores por pregunta."""
    fields = fields_by_id(definition)
    cleaned: dict[str, Any] = {}
    errors: list[ErrorDetail] = []
    for field_id, value in values.items():
        field = fields.get(field_id)
        if field is None:
            errors.append(ErrorDetail("unknown_field", UNKNOWN_FIELD_MESSAGE, field_id=field_id))
            continue
        if value is None:
            continue
        if field.type in NO_VALUE_FIELD_TYPES:
            errors.append(ErrorDetail("invalid_value", NO_VALUE_MESSAGE, field_id=field_id))
            continue
        try:
            if field.type == FieldType.SELECT:
                result = _clean_select(value, field)
            else:
                cleaner = CLEANERS.get(field.type)
                if cleaner is None:
                    raise InvalidAnswer("Este tipo de pregunta no acepta una respuesta directa.")
                result = cleaner(value)
        except InvalidAnswer as error:
            errors.append(ErrorDetail("invalid_value", str(error), field_id=field_id))
            continue
        if result is not None:
            cleaned[field_id] = result
    return cleaned, errors


def _is_answered(field: FieldDefinition, values: dict[str, Any], photo_field_ids: set[str]) -> bool:
    if field.type == FieldType.PHOTO:
        return field.id in photo_field_ids
    if field.type == FieldType.CHECKBOX:
        # Una casilla obligatoria significa que hay que marcarla
        return values.get(field.id) is True
    return field.id in values


def missing_required(
    definition: FormDefinition, values: dict[str, Any], photo_field_ids: set[str]
) -> list[ErrorDetail]:
    """Preguntas obligatorias sin contestar. values ya debe venir limpio (clean_values)."""
    return [
        ErrorDetail("required", REQUIRED_MESSAGE, field_id=field.id)
        for section in definition.sections
        for field in section.fields
        if field.required
        and field.type not in NOT_REQUIRED_ON_SUBMIT
        and not _is_answered(field, values, photo_field_ids)
    ]


def accepts_photos(field: FieldDefinition) -> bool:
    return field.type == FieldType.PHOTO or field.allow_evidence
