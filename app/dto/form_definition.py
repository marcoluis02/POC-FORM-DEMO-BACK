from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.field_types import OPTION_FIELD_TYPES, UNIT_FIELD_TYPES, FieldType

SECTION_ID_PATTERN = r"^s_\d{3,6}$"
FIELD_ID_PATTERN = r"^f_\d{3,6}$"
TITLE_MAX_LENGTH = 200
LABEL_MAX_LENGTH = 300
UNIT_MAX_LENGTH = 20
OPTION_VALUE_MAX_LENGTH = 100
OPTION_LABEL_MAX_LENGTH = 200
MAX_SECTIONS = 50
MAX_FIELDS_PER_SECTION = 200
MIN_OPTIONS = 2
MAX_OPTIONS = 30


class StrictModel(BaseModel):
    """No acepta llaves desconocidas y limpia espacios de los textos."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def find_repeated(values: list) -> list:
    seen, repeated = set(), []
    for value in values:
        if value in seen and value not in repeated:
            repeated.append(value)
        seen.add(value)
    return repeated


class FieldOption(StrictModel):
    """Una opción de una pregunta tipo lista (select)."""

    value: str = Field(min_length=1, max_length=OPTION_VALUE_MAX_LENGTH)
    label: str = Field(min_length=1, max_length=OPTION_LABEL_MAX_LENGTH)


class FieldInput(StrictModel):
    id: str | None = Field(default=None, pattern=FIELD_ID_PATTERN)
    type: FieldType
    label: str = Field(min_length=1, max_length=LABEL_MAX_LENGTH)
    required: bool = False
    position: int = Field(ge=1)
    allow_evidence: bool = False
    unit: str | None = Field(default=None, max_length=UNIT_MAX_LENGTH)
    # Solo aplica a type=select. En el resto debe ir vacío o no mandarse.
    options: list[FieldOption] | None = None

    @field_validator("unit", mode="before")
    @classmethod
    def empty_unit_is_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("options", mode="before")
    @classmethod
    def empty_options_are_none(cls, value):
        if value is None or value == []:
            return None
        return value

    @model_validator(mode="after")
    def unit_and_options_match_type(self):
        if self.unit is not None and self.type not in UNIT_FIELD_TYPES:
            raise ValueError("La unidad solo aplica a campos de tipo número.")

        if self.type in OPTION_FIELD_TYPES:
            if self.options is None:
                raise ValueError("Las preguntas de lista necesitan al menos 2 opciones.")
            if len(self.options) < MIN_OPTIONS:
                raise ValueError(f"Las preguntas de lista necesitan al menos {MIN_OPTIONS} opciones.")
            if len(self.options) > MAX_OPTIONS:
                raise ValueError(f"Una pregunta de lista no puede tener más de {MAX_OPTIONS} opciones.")
            repeated = find_repeated([option.value for option in self.options])
            if repeated:
                raise ValueError(f"Hay opciones con el mismo valor: {', '.join(repeated)}.")
        elif self.options is not None:
            raise ValueError("Las opciones solo aplican a preguntas de tipo lista (select).")
        return self


class SectionInput(StrictModel):
    id: str | None = Field(default=None, pattern=SECTION_ID_PATTERN)
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    position: int = Field(ge=1)
    fields: list[FieldInput] = Field(min_length=1, max_length=MAX_FIELDS_PER_SECTION)

    @model_validator(mode="after")
    def field_positions_are_unique(self):
        if find_repeated([f.position for f in self.fields]):
            raise ValueError(f"La sección '{self.title}' tiene campos con la misma posición.")
        return self


class FormDefinitionInput(StrictModel):
    """Lo que manda el cliente. Los ids son opcionales: el backend genera los que falten."""

    schema_version: Literal[1]
    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    sections: list[SectionInput] = Field(min_length=1, max_length=MAX_SECTIONS)

    @model_validator(mode="after")
    def ids_and_positions_are_unique(self):
        if find_repeated([s.position for s in self.sections]):
            raise ValueError("Hay secciones con la misma posición.")

        repeated_sections = find_repeated([s.id for s in self.sections if s.id])
        if repeated_sections:
            raise ValueError(f"Hay secciones con el mismo id: {', '.join(repeated_sections)}.")

        repeated_fields = find_repeated([f.id for s in self.sections for f in s.fields if f.id])
        if repeated_fields:
            raise ValueError(f"Hay campos con el mismo id: {', '.join(repeated_fields)}.")
        return self


class FieldDefinition(FieldInput):
    id: str = Field(pattern=FIELD_ID_PATTERN)


class SectionDefinition(SectionInput):
    id: str = Field(pattern=SECTION_ID_PATTERN)
    fields: list[FieldDefinition] = Field(min_length=1, max_length=MAX_FIELDS_PER_SECTION)


def is_consecutive(positions: list[int]) -> bool:
    return positions == list(range(1, len(positions) + 1))


class FormDefinition(FormDefinitionInput):
    """Definición confirmada: todas las secciones y campos ya tienen id estable
    y sus posiciones son consecutivas (1, 2, 3...). normalize_definition la deja así."""

    sections: list[SectionDefinition] = Field(min_length=1, max_length=MAX_SECTIONS)

    @model_validator(mode="after")
    def positions_are_consecutive(self):
        if not is_consecutive([s.position for s in self.sections]):
            raise ValueError("Las secciones deben tener posiciones 1, 2, 3... sin saltos.")
        for section in self.sections:
            if not is_consecutive([f.position for f in section.fields]):
                raise ValueError(
                    f"Los campos de la sección '{section.title}' deben tener posiciones 1, 2, 3... sin saltos."
                )
        return self
