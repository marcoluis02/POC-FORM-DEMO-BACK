import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.response_status import ResponseStatus
from app.models.base import Base, enum_check
from app.models.mixins.timestamp_mixin import TimestampMixin


class FormResponse(TimestampMixin, Base):
    __tablename__ = "form_responses"
    __table_args__ = (
        enum_check("status", ResponseStatus, "status_valid"),
        # Listado por plantilla: WHERE template_id = ? ORDER BY created_at DESC, id DESC
        Index("ix_form_responses_template_id_created_at_id", "template_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Se guarda también la plantilla para listar sin unir con las versiones
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="RESTRICT"), nullable=False
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_demo_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    # Nombre que le pone el usuario a este llenado (se ve en el listado)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # { "f_001": "yes", "f_002": 72.5 } — las fotos van en attachments
    values_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
