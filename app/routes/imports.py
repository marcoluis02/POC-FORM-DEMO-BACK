import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.config import get_settings
from app.dto.common import ErrorResponseOut
from app.dto.imports import ImportOut
from app.factories.services_factory import get_import_service
from app.routes.dependencies import IdempotencyKeyHeader
from app.services.import_service import ImportService

settings = get_settings()
router = APIRouter(prefix=f"{settings.api_prefix}/imports", tags=["imports"])

ServiceDep = Annotated[ImportService, Depends(get_import_service)]
ERRORS = {code: {"model": ErrorResponseOut} for code in (404, 409, 413, 422, 429, 503)}


@router.post("", response_model=ImportOut, status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_import(
    service: ServiceDep,
    file: Annotated[UploadFile, File(description="Foto (JPG, PNG, WEBP) o PDF del formato original")],
    idempotency_key: IdempotencyKeyHeader = None,
) -> ImportOut:
    try:
        # Se lee 1 byte de más para saber si se pasó del límite sin cargar todo el archivo
        content = await file.read(settings.max_upload_bytes + 1)
    finally:
        await file.close()
    return await service.create_import(file.filename, content, idempotency_key)


@router.get("/{import_id}", response_model=ImportOut, responses=ERRORS)
async def get_import(import_id: uuid.UUID, service: ServiceDep) -> ImportOut:
    return await service.get_import(import_id)
