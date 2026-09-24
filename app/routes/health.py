from typing import Annotated

from fastapi import APIRouter, Depends

from app.dto.common import ErrorResponseOut
from app.dto.health import HealthOut
from app.factories.services_factory import get_health_service
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])

HEALTH_ERRORS = {429: {"model": ErrorResponseOut}, 503: {"model": ErrorResponseOut}}


@router.get("/health", response_model=HealthOut, responses=HEALTH_ERRORS)
async def health(service: Annotated[HealthService, Depends(get_health_service)]) -> HealthOut:
    return await service.check()
