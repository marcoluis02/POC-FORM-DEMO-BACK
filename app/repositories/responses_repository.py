import uuid
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import load_only

from app.models.form_response import FormResponse
from app.models.form_template_version import FormTemplateVersion
from app.repositories.base_repository import BaseRepository

# Columnas del listado: no se trae values_json (puede ser grande)
SUMMARY_COLUMNS = (
    FormResponse.id,
    FormResponse.template_id,
    FormResponse.template_version_id,
    FormResponse.name,
    FormResponse.status,
    FormResponse.submitted_at,
    FormResponse.created_at,
    FormResponse.updated_at,
)


class ResponsesRepository(BaseRepository[FormResponse]):
    model = FormResponse

    async def get_with_version_number(self, response_id: uuid.UUID) -> tuple[FormResponse, int] | None:
        """Respuesta y el número de versión de su plantilla en una sola consulta."""
        stmt = (
            select(FormResponse, FormTemplateVersion.version)
            .join(FormTemplateVersion, FormTemplateVersion.id == FormResponse.template_version_id)
            .where(FormResponse.id == response_id)
        )
        row = (await self._session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def get_with_version(
        self, response_id: uuid.UUID, *, lock: bool = False
    ) -> tuple[FormResponse, FormTemplateVersion] | None:
        """Respuesta con su versión (trae la definición para validar).
        lock=True bloquea solo la fila de la respuesta para que dos cambios no se pisen."""
        stmt = (
            select(FormResponse, FormTemplateVersion)
            .join(FormTemplateVersion, FormTemplateVersion.id == FormResponse.template_version_id)
            .where(FormResponse.id == response_id)
        )
        if lock:
            stmt = stmt.with_for_update(of=FormResponse)
        row = (await self._session.execute(stmt)).first()
        return (row[0], row[1]) if row else None

    async def list_page(
        self, template_id: uuid.UUID, limit: int, after: tuple[datetime, uuid.UUID] | None
    ) -> list[tuple[FormResponse, int]]:
        """Respuestas de una plantilla, de la más nueva a la más vieja, con su número de versión.
        Una sola consulta que usa el índice (template_id, created_at, id)."""
        stmt = (
            select(FormResponse, FormTemplateVersion.version)
            .join(FormTemplateVersion, FormTemplateVersion.id == FormResponse.template_version_id)
            .options(load_only(*SUMMARY_COLUMNS, raiseload=True))
            .where(FormResponse.template_id == template_id)
            .order_by(FormResponse.created_at.desc(), FormResponse.id.desc())
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(tuple_(FormResponse.created_at, FormResponse.id) < tuple_(*after))
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]
