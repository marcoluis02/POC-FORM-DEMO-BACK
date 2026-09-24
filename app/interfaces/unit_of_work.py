from collections.abc import Callable
from typing import Protocol, Self

from app.interfaces.idempotency_repository import IdempotencyRepositoryInterface
from app.interfaces.imports_repository import ImportsRepositoryInterface
from app.interfaces.templates_repository import TemplatesRepositoryInterface
from app.interfaces.worker_tasks_repository import WorkerTasksRepositoryInterface


class UnitOfWorkInterface(Protocol):
    imports: ImportsRepositoryInterface
    templates: TemplatesRepositoryInterface
    idempotency: IdempotencyRepositoryInterface
    worker_tasks: WorkerTasksRepositoryInterface

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    async def commit(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWorkInterface]
