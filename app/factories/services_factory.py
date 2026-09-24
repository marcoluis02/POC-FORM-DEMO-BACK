from app.core.database import get_session_factory
from app.services.health_service import HealthService


def get_health_service() -> HealthService:
    return HealthService(get_session_factory())
