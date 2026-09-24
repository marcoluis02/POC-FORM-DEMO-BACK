import uuid
from datetime import datetime
from typing import Protocol

from app.models.form_response import FormResponse
from app.models.form_template_version import FormTemplateVersion


class ResponsesRepositoryInterface(Protocol):
    async def add(self, entity: FormResponse) -> FormResponse: ...

    async def update(self, entity: FormResponse) -> FormResponse: ...

    async def get_with_version_number(self, response_id: uuid.UUID) -> tuple[FormResponse, int] | None: ...

    async def get_with_version(
        self, response_id: uuid.UUID, *, lock: bool = False
    ) -> tuple[FormResponse, FormTemplateVersion] | None: ...

    async def list_page(
        self, template_id: uuid.UUID, limit: int, after: tuple[datetime, uuid.UUID] | None
    ) -> list[tuple[FormResponse, int]]: ...
