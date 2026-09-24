import uuid

from app.domain.template_status import TemplateStatus
from app.dto.form_definition import FormDefinition
from app.dto.templates import TemplateOut, TemplateSummaryOut, TemplateVersionOut
from app.models.form_template import FormTemplate
from app.models.form_template_version import FormTemplateVersion

FIRST_VERSION = 1


def build_new_template(
    definition: FormDefinition, source_import_id: uuid.UUID | None
) -> tuple[FormTemplate, FormTemplateVersion]:
    template = FormTemplate(
        id=uuid.uuid4(),
        name=definition.title,
        status=TemplateStatus.ACTIVE,
        latest_version=FIRST_VERSION,
    )
    version = build_version(template, definition, FIRST_VERSION, source_import_id)
    return template, version


def build_version(
    template: FormTemplate, definition: FormDefinition, number: int, source_import_id: uuid.UUID | None
) -> FormTemplateVersion:
    return FormTemplateVersion(
        id=uuid.uuid4(),
        template_id=template.id,
        version=number,
        definition_json=definition.model_dump(mode="json"),
        source_import_id=source_import_id,
    )


def to_version_out(version: FormTemplateVersion) -> TemplateVersionOut:
    return TemplateVersionOut(
        id=version.id,
        template_id=version.template_id,
        version=version.version,
        definition=FormDefinition.model_validate(version.definition_json),
        source_import_id=version.source_import_id,
        created_at=version.created_at,
    )


def to_template_summary_out(template: FormTemplate) -> TemplateSummaryOut:
    return TemplateSummaryOut(
        id=template.id,
        name=template.name,
        status=template.status,
        latest_version=template.latest_version,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def to_template_out(template: FormTemplate, version: FormTemplateVersion) -> TemplateOut:
    return TemplateOut(
        **to_template_summary_out(template).model_dump(),
        current_version=to_version_out(version),
    )
