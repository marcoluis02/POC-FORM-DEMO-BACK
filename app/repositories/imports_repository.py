import uuid

from sqlalchemy import select

from app.models.form_import import FormImport
from app.repositories.base_repository import BaseRepository


class ImportsRepository(BaseRepository[FormImport]):
    model = FormImport

    async def get_for_update(self, import_id: uuid.UUID) -> FormImport | None:
        stmt = select(FormImport).where(FormImport.id == import_id).with_for_update()
        return (await self._session.scalars(stmt)).first()
