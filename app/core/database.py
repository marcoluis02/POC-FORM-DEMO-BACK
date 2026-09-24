import socket
from functools import lru_cache

from asyncpg.exceptions import InsufficientResourcesError, PostgresConnectionError
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings

# Errores que significan "la BD no está disponible" (caída, sin conexiones libres, pool lleno, red)
DATABASE_UNAVAILABLE_ERRORS: tuple[type[Exception], ...] = (
    OperationalError,
    InterfaceError,
    PoolTimeoutError,
    InsufficientResourcesError,
    PostgresConnectionError,
    ConnectionError,
    TimeoutError,
    socket.gaierror,
)


def build_connect_args(settings: Settings) -> dict:
    """Cada conexión usa SSL, corta consultas lentas y trabaja en UTC."""
    return {
        "ssl": settings.db_ssl_mode,
        "server_settings": {
            "statement_timeout": str(settings.db_statement_timeout_ms),
            "timezone": "UTC",
        },
    }


def build_engine(settings: Settings, pool_size: int, max_overflow: int) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=True,
        connect_args=build_connect_args(settings),
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Un solo engine (y un solo pool) por proceso para la API. Se crea la primera vez que se usa."""
    settings = get_settings()
    return build_engine(settings, settings.db_pool_size, settings.db_max_overflow)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return build_session_factory(get_engine())


async def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
