from app.dto.form_definition import FormDefinition


def count_definition_corrections(original: FormDefinition, revised: FormDefinition) -> int:
    """Cuenta cambios útiles para la métrica de la POC.

    No intenta reconstruir cada clic del usuario. Cuenta una corrección por elemento lógico:
    título, sección agregada/eliminada/modificada o campo agregado/eliminado/modificado.
    """
    corrections = int(original.title != revised.title)

    original_sections = {section.id: section for section in original.sections}
    revised_sections = {section.id: section for section in revised.sections}

    corrections += len(original_sections.keys() - revised_sections.keys())
    corrections += len(revised_sections.keys() - original_sections.keys())

    for section_id in original_sections.keys() & revised_sections.keys():
        before_section = original_sections[section_id]
        after_section = revised_sections[section_id]
        if (before_section.title, before_section.position) != (after_section.title, after_section.position):
            corrections += 1

        before_fields = {field.id: field for field in before_section.fields}
        after_fields = {field.id: field for field in after_section.fields}
        corrections += len(before_fields.keys() - after_fields.keys())
        corrections += len(after_fields.keys() - before_fields.keys())

        for field_id in before_fields.keys() & after_fields.keys():
            before = before_fields[field_id].model_dump(mode="json", exclude={"id"})
            after = after_fields[field_id].model_dump(mode="json", exclude={"id"})
            if before != after:
                corrections += 1

    return corrections
