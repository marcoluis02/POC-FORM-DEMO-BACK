import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.worker_task_status import WorkerTaskStatus
from app.models.base import Base, enum_check
from app.models.mixins.timestamp_mixin import TimestampMixin
from app.utils.time import utc_now


class WorkerTask(TimestampMixin, Base):
    """Tabla de apoyo: la API deja tareas en pending y el worker las procesa."""

    __tablename__ = "worker_tasks"
    __table_args__ = (
        enum_check("status", WorkerTaskStatus, "status_valid"),
        # El worker busca: status = pending AND available_at <= ahora, en orden
        Index("ix_worker_tasks_status_available_at", "status", "available_at"),
        # Evita duplicar una misma tarea mientras sigue pendiente o en proceso
        Index(
            "uq_worker_tasks_active_dedupe_key",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing') AND dedupe_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
