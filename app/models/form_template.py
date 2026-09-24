import uuid

from sqlalchemy import CheckConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.template_status import TemplateStatus
from app.models.base import Base, enum_check
from app.models.mixins.timestamp_mixin import TimestampMixin


class FormTemplate(TimestampMixin, Base):
    __tablename__ = "form_templates"
    __table_args__ = (
        enum_check("status", TemplateStatus, "status_valid"),
        CheckConstraint("latest_version >= 1", name="latest_version_positive"),
        # Listado paginado: ORDER BY created_at DESC, id DESC
        Index("ix_form_templates_created_at_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False)
