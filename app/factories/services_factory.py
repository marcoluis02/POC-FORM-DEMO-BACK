from functools import lru_cache

from app.cloud.s3_storage import S3Storage
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.unit_of_work import UnitOfWork
from app.services.health_service import HealthService
from app.services.idempotency_service import IdempotencyService
from app.services.import_service import ImportService
from app.services.template_service import TemplateService


def build_uow() -> UnitOfWork:
    return UnitOfWork(get_session_factory())


@lru_cache
def get_storage() -> S3Storage:
    """Un solo cliente S3 (y su pool de conexiones) por proceso."""
    return S3Storage(get_settings())


def get_health_service() -> HealthService:
    return HealthService(get_session_factory())


def get_idempotency_service() -> IdempotencyService:
    return IdempotencyService(build_uow, get_settings().idempotency_ttl_hours)


def get_template_service() -> TemplateService:
    return TemplateService(build_uow, get_idempotency_service())


def get_import_service() -> ImportService:
    settings = get_settings()
    return ImportService(
        build_uow, get_idempotency_service(), get_storage(), settings.max_upload_bytes, settings.max_pdf_pages
    )
