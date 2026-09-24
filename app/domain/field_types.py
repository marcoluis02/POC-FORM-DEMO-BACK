from enum import StrEnum


class FieldType(StrEnum):
    CHECKBOX = "checkbox"
    YES_NO_NA = "yes_no_na"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    DATE = "date"
    PHOTO = "photo"
    SIGNATURE_PLACEHOLDER = "signature_placeholder"


# Solo los campos de número aceptan unidad (°F, kg, psi...)
UNIT_FIELD_TYPES = frozenset({FieldType.NUMBER})
