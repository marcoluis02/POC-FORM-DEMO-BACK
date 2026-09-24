import re
from collections.abc import Iterable

from app.dto.form_definition import FormDefinition, FormDefinitionInput

ID_NUMBER = re.compile(r"_(\d+)$")


def _max_number(ids: Iterable[str | None]) -> int:
    numbers = [int(match.group(1)) for value in ids if value and (match := ID_NUMBER.search(value))]
    return max(numbers, default=0)


def _ids_of(definition: FormDefinitionInput | None) -> tuple[list[str | None], list[str | None]]:
    if definition is None:
        return [], []
    section_ids = [section.id for section in definition.sections]
    field_ids = [field.id for section in definition.sections for field in section.fields]
    return section_ids, field_ids


def normalize_definition(data: FormDefinitionInput, previous: FormDefinition | None = None) -> FormDefinition:
    """Deja la definición lista para guardarse:
    - genera ids a secciones y campos nuevos sin reutilizar ids de la versión anterior
    - ordena por posición y deja posiciones consecutivas (1, 2, 3...)"""
    new_section_ids, new_field_ids = _ids_of(data)
    old_section_ids, old_field_ids = _ids_of(previous)
    next_section = _max_number(new_section_ids + old_section_ids) + 1
    next_field = _max_number(new_field_ids + old_field_ids) + 1

    sections = []
    for section_position, section in enumerate(sorted(data.sections, key=lambda s: s.position), start=1):
        fields = []
        for field_position, field in enumerate(sorted(section.fields, key=lambda f: f.position), start=1):
            field_id = field.id
            if field_id is None:
                field_id = f"f_{next_field:03d}"
                next_field += 1
            fields.append({**field.model_dump(), "id": field_id, "position": field_position})

        section_id = section.id
        if section_id is None:
            section_id = f"s_{next_section:03d}"
            next_section += 1
        sections.append({"id": section_id, "title": section.title, "position": section_position, "fields": fields})

    return FormDefinition.model_validate(
        {"schema_version": data.schema_version, "title": data.title, "sections": sections}
    )
