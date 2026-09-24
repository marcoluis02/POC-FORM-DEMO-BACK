import copy
import json
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.idempotency_service import IdempotencyService
from app.services.import_service import ImportService
from app.services.template_service import TemplateService
from tests.fakes.fake_unit_of_work import FakeDatabase, FakeStorage, FakeUnitOfWork
from tests.fakes.sample_files import PNG_BYTES, make_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"
IDEMPOTENCY_TTL_HOURS = 24
TEST_MAX_UPLOAD_BYTES = 8192
TEST_MAX_PDF_PAGES = 3

PDF_BYTES = make_pdf(pages=1)

__all__ = ["PDF_BYTES", "PNG_BYTES", "TEST_MAX_PDF_PAGES", "TEST_MAX_UPLOAD_BYTES"]


@pytest.fixture(scope="session")
def _maintenance_template_raw() -> dict:
    return json.loads((FIXTURES_DIR / "maintenance_template.json").read_text(encoding="utf-8"))


@pytest.fixture
def maintenance_template(_maintenance_template_raw: dict) -> dict:
    """Copia nueva en cada test para poder modificarla sin afectar a otros."""
    return copy.deepcopy(_maintenance_template_raw)


@pytest.fixture
async def client():
    """Cliente HTTP contra la app. Cada test usa una IP distinta para que el rate limit no se mezcle entre tests."""
    fake_ip = f"10.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}.{uuid.uuid4().int % 250}"
    transport = ASGITransport(app=app, raise_app_exceptions=False, client=(fake_ip, 5000))
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
