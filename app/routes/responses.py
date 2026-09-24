import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.core.config import get_settings
from app.dto.common import ErrorResponseOut
from app.dto.form_definition import FIELD_ID_PATTERN
from app.dto.responses import (
    AttachmentDeletedOut,
    AttachmentOut,
    ResponseCreateIn,
    ResponseOut,
    ResponsePageOut,
    ResponseValuesIn,
)
from app.factories.services_factory import get_response_service
from app.routes.dependencies import CursorQuery, IdempotencyKeyHeader
from app.services.response_service import ResponseService

settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/responses", tags=["responses"])

ServiceDep = Annotated[ResponseService, Depends(get_response_service)]
ERRORS = {code: {"model": ErrorResponseOut} for code in (404, 409, 413, 422, 429, 503)}


@router.get("", response_model=ResponsePageOut, responses=ERRORS)
async def list_responses(
    service: ServiceDep,
    template_id: Annotated[uuid.UUID, Query()],
    limit: Annotated[int, Query(ge=1, le=settings.pagination_max_limit)] = settings.pagination_default_limit,
    cursor: CursorQuery = None,
) -> ResponsePageOut:
    return await service.list_responses(template_id, limit, cursor)


@router.post("", response_model=ResponseOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_response(
    body: ResponseCreateIn, service: ServiceDep, idempotency_key: IdempotencyKeyHeader = None
) -> ResponseOut:
    return await service.create_response(body, idempotency_key)


@router.get("/{response_id}", response_model=ResponseOut, responses=ERRORS)
async def get_response(response_id: uuid.UUID, service: ServiceDep) -> ResponseOut:
    return await service.get_response(response_id)


@router.put("/{response_id}", response_model=ResponseOut, responses=ERRORS)
async def save_draft(
    response_id: uuid.UUID, body: ResponseValuesIn, service: ServiceDep, idempotency_key: IdempotencyKeyHeader = None
) -> ResponseOut:
    return await service.save_draft(response_id, body, idempotency_key)


@router.post("/{response_id}/submit", response_model=ResponseOut, responses=ERRORS)
async def submit_response(
    response_id: uuid.UUID, body: ResponseValuesIn, service: ServiceDep, idempotency_key: IdempotencyKeyHeader = None
) -> ResponseOut:
    return await service.submit(response_id, body, idempotency_key)


@router.post(
    "/{response_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
async def add_attachment(
    response_id: uuid.UUID,
    service: ServiceDep,
    field_id: Annotated[str, Form(pattern=FIELD_ID_PATTERN, description="Pregunta a la que pertenece la foto")],
    file: Annotated[UploadFile, File(description="Foto JPG, PNG o WEBP")],
    idempotency_key: IdempotencyKeyHeader = None,
) -> AttachmentOut:
    try:
        # Se lee 1 byte de más para saber si se pasó del límite sin cargar todo el archivo
        content = await file.read(settings.max_upload_bytes + 1)
    finally:
        await file.close()
    return await service.add_attachment(response_id, field_id, file.filename, content, idempotency_key)


@router.delete("/{response_id}/attachments/{attachment_id}", response_model=AttachmentDeletedOut, responses=ERRORS)
async def delete_attachment(
    response_id: uuid.UUID,
    attachment_id: uuid.UUID,
    service: ServiceDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> AttachmentDeletedOut:
    return await service.delete_attachment(response_id, attachment_id, idempotency_key)
