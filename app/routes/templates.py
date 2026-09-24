import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.config import get_settings
from app.dto.common import ErrorResponseOut
from app.dto.form_definition import FormDefinitionInput
from app.dto.templates import TemplateOut, TemplatePageOut, TemplateVersionOut
from app.factories.services_factory import get_template_service
from app.routes.dependencies import IdempotencyKeyHeader
from app.services.template_service import TemplateService

settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/templates", tags=["templates"])

ServiceDep = Annotated[TemplateService, Depends(get_template_service)]
ERRORS = {code: {"model": ErrorResponseOut} for code in (404, 409, 422, 429, 503)}
CURSOR_MAX_LENGTH = 500
# Documento original (lo regresa POST /imports). Opcional para no romper a quien no lo manda.
SourceImportQuery = Annotated[uuid.UUID | None, Query()]


@router.get("", response_model=TemplatePageOut, responses=ERRORS)
async def list_templates(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=settings.pagination_max_limit)] = settings.pagination_default_limit,
    cursor: Annotated[str | None, Query(min_length=1, max_length=CURSOR_MAX_LENGTH)] = None,
) -> TemplatePageOut:
    return await service.list_templates(limit, cursor)


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_template(
    body: FormDefinitionInput,
    service: ServiceDep,
    idempotency_key: IdempotencyKeyHeader = None,
    source_import_id: SourceImportQuery = None,
) -> TemplateOut:
    return await service.create_template(body, idempotency_key, source_import_id)


@router.get("/{template_id}", response_model=TemplateOut, responses=ERRORS)
async def get_template(template_id: uuid.UUID, service: ServiceDep) -> TemplateOut:
    return await service.get_template(template_id)


@router.get("/{template_id}/versions/{version}", response_model=TemplateVersionOut, responses=ERRORS)
async def get_template_version(
    template_id: uuid.UUID, version: Annotated[int, Path(ge=1)], service: ServiceDep
) -> TemplateVersionOut:
    return await service.get_version(template_id, version)


@router.post(
    "/{template_id}/versions", response_model=TemplateOut, status_code=status.HTTP_201_CREATED, responses=ERRORS
)
async def create_template_version(
    template_id: uuid.UUID,
    body: FormDefinitionInput,
    service: ServiceDep,
    idempotency_key: IdempotencyKeyHeader = None,
    source_import_id: SourceImportQuery = None,
) -> TemplateOut:
    return await service.create_version(template_id, body, idempotency_key, source_import_id)
