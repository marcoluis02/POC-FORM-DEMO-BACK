import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.response_status import ResponseStatus
from app.models.base import Base, enum_check
from app.models.mixins.timestamp_mixin import TimestampMixin


class FormResponse(TimestampMixin, Base):
    __tablename__ = "form_responses"
    __table_args__ = (enum_check("status", ResponseStatus, "status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_template_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_demo_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    values_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
