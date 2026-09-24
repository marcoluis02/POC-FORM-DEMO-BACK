import uuid
from typing import Protocol

from app.models.form_import import FormImport


class ImportsRepositoryInterface(Protocol):
    async def add(self, entity: FormImport) -> FormImport: ...

    async def get(self, entity_id: uuid.UUID) -> FormImport | None: ...
