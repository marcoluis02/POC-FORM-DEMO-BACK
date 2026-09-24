import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.database import build_connect_args

# app.models es el registro: importa todos los modelos. Si solo se importara Base,
# la metadata quedaría vacía y el autogenerate propondría borrar las tablas.
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
settings = get_settings()


def skip_empty_revision(migration_context, revision, directives) -> None:
    """Con --autogenerate, si no hay cambios en los modelos no se crea un archivo vacío."""
    cmd_opts = config.cmd_opts
    if not (cmd_opts and getattr(cmd_opts, "autogenerate", False)):
        return
    if directives and directives[0].upgrade_ops.is_empty():
        directives[:] = []
        print("No hay cambios en los modelos: no se creó ninguna migración.")


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        process_revision_directives=skip_empty_revision,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        process_revision_directives=skip_empty_revision,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # NullPool: la migración abre una sola conexión y la cierra al terminar
    engine = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        connect_args=build_connect_args(settings),
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
