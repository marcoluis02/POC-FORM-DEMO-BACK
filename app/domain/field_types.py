from enum import StrEnum


class FieldType(StrEnum):
    CHECKBOX = "checkbox"
    YES_NO_NA = "yes_no_na"
    SELECT = "select"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    DATE = "date"
    PHOTO = "photo"
    SIGNATURE_PLACEHOLDER = "signature_placeholder"


# Solo los campos de número aceptan unidad (°F, kg, psi...)
UNIT_FIELD_TYPES = frozenset({FieldType.NUMBER})

# Solo "select" lleva lista de opciones (Sí/No/NA tiene las suyas fijas)
OPTION_FIELD_TYPES = frozenset({FieldType.SELECT})
