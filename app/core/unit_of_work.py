from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.attachments_repository import AttachmentsRepository
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.imports_repository import ImportsRepository
from app.repositories.responses_repository import ResponsesRepository
from app.repositories.templates_repository import TemplatesRepository
from app.repositories.worker_tasks_repository import WorkerTasksRepository


class UnitOfWork:
    """Una sesión por operación. Un solo commit; si algo falla hace rollback y siempre cierra la sesión."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def __aenter__(self) -> "UnitOfWork":
        self._session = self._session_factory()
        self.imports = ImportsRepository(self._session)
        self.templates = TemplatesRepository(self._session)
        self.responses = ResponsesRepository(self._session)
        self.attachments = AttachmentsRepository(self._session)
        self.idempotency = IdempotencyRepository(self._session)
        self.worker_tasks = WorkerTasksRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
