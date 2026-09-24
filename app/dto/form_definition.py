from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.field_types import UNIT_FIELD_TYPES, FieldType

SECTION_ID_PATTERN = r"^s_\d{3,6}$"
FIELD_ID_PATTERN = r"^f_\d{3,6}$"
TITLE_MAX_LENGTH = 200
LABEL_MAX_LENGTH = 300
UNIT_MAX_LENGTH = 20
MAX_SECTIONS = 50
MAX_FIELDS_PER_SECTION = 200


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


class FieldInput(StrictModel):
    id: str | None = Field(default=None, pattern=FIELD_ID_PATTERN)
    type: FieldType
    label: str = Field(min_length=1, max_length=LABEL_MAX_LENGTH)
    required: bool = False
    position: int = Field(ge=1)
    allow_evidence: bool = False
    unit: str | None = Field(default=None, max_length=UNIT_MAX_LENGTH)

    @field_validator("unit", mode="before")
    @classmethod
    def empty_unit_is_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def unit_only_for_numbers(self):
        if self.unit is not None and self.type not in UNIT_FIELD_TYPES:
            raise ValueError("La unidad solo aplica a campos de tipo número.")
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


class FormDefinition(FormDefinitionInput):
    """Definición confirmada: todas las secciones y campos ya tienen id estable."""

    sections: list[SectionDefinition] = Field(min_length=1, max_length=MAX_SECTIONS)
