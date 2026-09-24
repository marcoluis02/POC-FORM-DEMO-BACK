import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.import_status import ImportStatus
from app.models.base import Base, enum_check
from app.models.mixins.timestamp_mixin import TimestampMixin


class FormImport(TimestampMixin, Base):
    """Documento subido (foto/PDF) y el borrador que extrae la IA."""

    __tablename__ = "form_imports"
    __table_args__ = (enum_check("status", ImportStatus, "status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    original_file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    draft_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    detected_fields_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corrections_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
