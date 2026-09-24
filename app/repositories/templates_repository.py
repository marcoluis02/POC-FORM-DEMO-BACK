import uuid
from datetime import datetime

from sqlalchemy import and_, select, tuple_

from app.models.form_template import FormTemplate
from app.models.form_template_version import FormTemplateVersion
from app.repositories.base_repository import BaseRepository


class TemplatesRepository(BaseRepository[FormTemplate]):
    model = FormTemplate

    async def add_version(self, version: FormTemplateVersion) -> FormTemplateVersion:
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_for_update(self, template_id: uuid.UUID) -> FormTemplate | None:
        """Bloquea la fila para que dos versiones nuevas no tomen el mismo número."""
        stmt = select(FormTemplate).where(FormTemplate.id == template_id).with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_with_latest_version(
        self, template_id: uuid.UUID
    ) -> tuple[FormTemplate, FormTemplateVersion] | None:
        """Plantilla y su última versión en una sola consulta."""
        stmt = (
            select(FormTemplate, FormTemplateVersion)
            .join(
                FormTemplateVersion,
                and_(
                    FormTemplateVersion.template_id == FormTemplate.id,
                    FormTemplateVersion.version == FormTemplate.latest_version,
                ),
            )
            .where(FormTemplate.id == template_id)
        )
        row = (await self._session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def list_page(
        self, limit: int, after: tuple[datetime, uuid.UUID] | None
    ) -> list[FormTemplate]:
        """Plantillas de la más nueva a la más vieja, una sola consulta sin las definiciones.
        after es la última fila de la página anterior (paginación por cursor, no usa OFFSET)."""
        stmt = select(FormTemplate).order_by(FormTemplate.created_at.desc(), FormTemplate.id.desc()).limit(limit)
        if after is not None:
            stmt = stmt.where(tuple_(FormTemplate.created_at, FormTemplate.id) < tuple_(*after))
        return list((await self._session.scalars(stmt)).all())

    async def get_version(self, template_id: uuid.UUID, version: int) -> FormTemplateVersion | None:
        stmt = select(FormTemplateVersion).where(
            FormTemplateVersion.template_id == template_id,
            FormTemplateVersion.version == version,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
