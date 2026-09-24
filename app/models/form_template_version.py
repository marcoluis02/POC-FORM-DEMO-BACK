import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins.timestamp_mixin import CreatedAtMixin


class FormTemplateVersion(CreatedAtMixin, Base):
    """Versión confirmada de una plantilla. Nunca se modifica: los cambios crean una versión nueva."""

    __tablename__ = "form_template_versions"
    __table_args__ = (
        # También sirve como índice para buscar por template_id
        UniqueConstraint("template_id", "version", name="uq_form_template_versions_template_id_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Documento original (foto/PDF) que se usó para esta versión
    source_import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_imports.id", ondelete="SET NULL"), nullable=True, index=True
    )
