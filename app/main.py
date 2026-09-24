from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.routes import health, imports, responses, templates
from app.security.body_size_middleware import BodySizeLimitMiddleware
from app.security.rate_limit_middleware import RateLimitMiddleware
from app.workers.worker_runner import WorkerRunner

# Espacio extra para los encabezados del multipart además del archivo
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    worker = WorkerRunner(settings) if settings.worker_enabled else None
    if worker:
        worker.start()
    try:
        yield
    finally:
        if worker:
            worker.stop()
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # El último middleware agregado es el primero en correr: CORS va afuera para que el 429 también lleve sus headers
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES,
        max_upload_mb=settings.max_upload_mb,
    )
    app.add_middleware(
        RateLimitMiddleware,
        limit=settings.rate_limit_default,
        storage_uri=settings.rate_limit_storage_uri,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(templates.router)
    app.include_router(imports.router)
    app.include_router(responses.router)
    return app


app = create_app()
