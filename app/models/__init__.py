# Importa todos los modelos para que Alembic los vea en Base.metadata
from app.models.attachment import Attachment
from app.models.base import Base
from app.models.form_import import FormImport
from app.models.form_response import FormResponse
from app.models.form_template import FormTemplate
from app.models.form_template_version import FormTemplateVersion
from app.models.idempotency_key import IdempotencyKey
from app.models.worker_task import WorkerTask

__all__ = [
    "Attachment",
    "Base",
    "FormImport",
    "FormResponse",
    "FormTemplate",
    "FormTemplateVersion",
    "IdempotencyKey",
    "WorkerTask",
]
