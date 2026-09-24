import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.attachment_type import AttachmentType
from app.models.base import Base, enum_check
from app.models.mixins.timestamp_mixin import CreatedAtMixin


class Attachment(CreatedAtMixin, Base):
    """Evidencia de una respuesta. Se guarda la llave del archivo, nunca una URL temporal."""

    __tablename__ = "attachments"
    __table_args__ = (
        enum_check("type", AttachmentType, "type_valid"),
        Index("ix_attachments_response_id_field_id", "response_id", "field_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_responses.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_key: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
