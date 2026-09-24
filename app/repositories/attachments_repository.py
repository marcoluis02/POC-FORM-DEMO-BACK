import uuid

from sqlalchemy import func, select

from app.models.attachment import Attachment
from app.repositories.base_repository import BaseRepository


class AttachmentsRepository(BaseRepository[Attachment]):
    model = Attachment

    async def list_for_response(self, response_id: uuid.UUID) -> list[Attachment]:
        """Todas las fotos de una respuesta en una sola consulta (usa el índice response_id, field_id)."""
        stmt = (
            select(Attachment)
            .where(Attachment.response_id == response_id)
            .order_by(Attachment.field_id, Attachment.created_at, Attachment.id)
        )
        return list((await self._session.scalars(stmt)).all())

    async def count_for_field(self, response_id: uuid.UUID, field_id: str) -> int:
        stmt = select(func.count()).where(Attachment.response_id == response_id, Attachment.field_id == field_id)
        return (await self._session.execute(stmt)).scalar_one()

    async def get_for_response(self, response_id: uuid.UUID, attachment_id: uuid.UUID) -> Attachment | None:
        stmt = select(Attachment).where(Attachment.id == attachment_id, Attachment.response_id == response_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()
