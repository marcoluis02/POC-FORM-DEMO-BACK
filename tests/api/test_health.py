import pytest
from asyncpg.exceptions import TooManyConnectionsError
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from app.dto.health import HealthOut
from app.factories.services_factory import get_health_service
from app.main import app


class HealthyService:
    async def check(self) -> HealthOut:
        return HealthOut(status="ok", database="ok")


class FullPoolService:
    async def check(self) -> HealthOut:
        raise PoolTimeoutError("pool lleno")


class TooManyClientsService:
    async def check(self) -> HealthOut:
        raise TooManyConnectionsError("sorry, too many clients already")


@pytest.fixture
async def client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def test_health_responde_ok(client):
    app.dependency_overrides[get_health_service] = HealthyService

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.parametrize("broken_service", [FullPoolService, TooManyClientsService])
async def test_health_devuelve_503_si_la_bd_no_esta_disponible(client, broken_service):
    app.dependency_overrides[get_health_service] = broken_service

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


async def test_ruta_inexistente_devuelve_error_con_forma_estandar(client):
    response = await client.get("/no-existe")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "No encontramos lo que buscas.", "details": []}
    }
