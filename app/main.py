from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.routes import health
from app.security.rate_limit_middleware import RateLimitMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # El último middleware agregado es el primero en correr: CORS va afuera para que el 429 también lleve sus headers
    app.add_middleware(
        RateLimitMiddleware,
        limit=settings.rate_limit_default,
        storage_uri=settings.rate_limit_storage_uri,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    register_exception_handlers(app)
    app.include_router(health.router)
    return app


app = create_app()
