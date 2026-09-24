from dataclasses import dataclass

from app.core.config import Settings
from app.interfaces.storage_provider import StorageProvider
from app.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True)
class TaskContext:
    """Lo que recibe cada handler: acceso a la BD (con el pool del worker), al storage y la configuración."""

    uow_factory: UnitOfWorkFactory
    settings: Settings
    storage: StorageProvider
