from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dto.health import HealthOut
from app.repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def check(self) -> HealthOut:
        async with self._session_factory() as session:
            await HealthRepository(session).ping()
        return HealthOut(status="ok", database="ok")
