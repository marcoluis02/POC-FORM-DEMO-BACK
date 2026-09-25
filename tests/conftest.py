import copy
import json
import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.idempotency_service import IdempotencyService
from app.services.import_service import ImportService
from app.services.response_service import ResponseService
from app.services.template_service import TemplateService
from tests.fakes.fake_extraction_provider import FakeExtractionProvider
from tests.fakes.fake_unit_of_work import FakeDatabase, FakeStorage, FakeUnitOfWork
from tests.fakes.sample_files import PNG_BYTES, make_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"
IDEMPOTENCY_TTL_HOURS = 24
TEST_MAX_UPLOAD_BYTES = 8192
TEST_MAX_PDF_PAGES = 3
TEST_MAX_PHOTOS_PER_FIELD = 2

PDF_BYTES = make_pdf(pages=1)

__all__ = ["PDF_BYTES", "PNG_BYTES", "TEST_MAX_PDF_PAGES", "TEST_MAX_PHOTOS_PER_FIELD", "TEST_MAX_UPLOAD_BYTES"]


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def _maintenance_template_raw() -> dict:
    return _load_fixture("maintenance_template.json")


@pytest.fixture
def maintenance_template(_maintenance_template_raw: dict) -> dict:
    """Copia nueva en cada test para poder modificarla sin afectar a otros."""
    return copy.deepcopy(_maintenance_template_raw)


@pytest.fixture(scope="session")
def _inspection_template_raw() -> dict:
    return _load_fixture("inspection_template.json")


@pytest.fixture
def inspection_template(_inspection_template_raw: dict) -> dict:
    """Plantilla con todos los tipos de pregunta (foto y firma obligatorias)."""
    return copy.deepcopy(_inspection_template_raw)


def _random_ip() -> str:
    return f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"


class RandomIpTransport(ASGITransport):
    """Cada petición sale de una IP distinta: el rate limit del .env no afecta estas pruebas
    (el rate limit tiene sus propias pruebas en test_rate_limit_middleware)."""

    async def handle_async_request(self, request):
        self.client = (_random_ip(), 5000)
        return await super().handle_async_request(request)


@pytest.fixture
async def client():
    """Cliente HTTP contra la app."""
    transport = RandomIpTransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest.fixture
def fake_db() -> FakeDatabase:
    return FakeDatabase()


@pytest.fixture
def uow_factory(fake_db: FakeDatabase):
    return lambda: FakeUnitOfWork(fake_db)


@pytest.fixture
def idempotency_service(uow_factory) -> IdempotencyService:
    return IdempotencyService(uow_factory, IDEMPOTENCY_TTL_HOURS)


@pytest.fixture
def template_service(uow_factory, idempotency_service) -> TemplateService:
    return TemplateService(uow_factory, idempotency_service)


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def import_service(uow_factory, idempotency_service, fake_storage) -> ImportService:
    return ImportService(uow_factory, idempotency_service, fake_storage, TEST_MAX_UPLOAD_BYTES, TEST_MAX_PDF_PAGES)


@pytest.fixture
def response_service(uow_factory, idempotency_service, fake_storage) -> ResponseService:
    return ResponseService(
        uow_factory, idempotency_service, fake_storage, TEST_MAX_UPLOAD_BYTES, TEST_MAX_PHOTOS_PER_FIELD
    )


@pytest.fixture
def fake_extraction_provider() -> FakeExtractionProvider:
    return FakeExtractionProvider()
