import uuid
from datetime import datetime
from typing import Any

from app.core.exceptions import IdempotencyKeyTakenError, StorageUnavailableError
from app.models.form_import import FormImport
from app.models.form_template import FormTemplate
from app.models.form_template_version import FormTemplateVersion
from app.models.idempotency_key import IdempotencyKey
from app.utils.time import utc_now


def _stamp(entity: Any) -> None:
    # En la BD esto lo pone el default de la columna
    now = utc_now()
    if hasattr(entity, "created_at") and entity.created_at is None:
        entity.created_at = now
    if hasattr(entity, "updated_at") and entity.updated_at is None:
        entity.updated_at = now


class FakeDatabase:
    """Tablas en memoria compartidas entre UoWs. Solo lo confirmado con commit queda guardado."""

    def __init__(self) -> None:
        self.imports: dict[uuid.UUID, FormImport] = {}
        self.templates: dict[uuid.UUID, FormTemplate] = {}
        self.versions: dict[tuple[uuid.UUID, int], FormTemplateVersion] = {}
        self.idempotency: dict[tuple[str, str], IdempotencyKey] = {}
        self.worker_tasks: list[dict[str, Any]] = []
        self.commits = 0


class FakeStorage:
    """Storage en memoria. fail=True simula que S3 no responde."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.put_calls = 0
        self.fail = False

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.put_calls += 1
        if self.fail:
            raise StorageUnavailableError("S3 no responde")
        self.objects[key] = (data, content_type)

    async def get_url(self, key: str) -> str:
        return f"https://storage.test/{key}?firma=temporal"


class FakeImportsRepository:
    def __init__(self, pending: dict[str, list[Any]], db: FakeDatabase):
        self._pending = pending
        self._db = db

    async def add(self, entity: FormImport) -> FormImport:
        _stamp(entity)
        self._pending["imports"].append(entity)
        return entity

    async def get(self, entity_id: uuid.UUID) -> FormImport | None:
        return self._db.imports.get(entity_id)


class FakeTemplatesRepository:
    def __init__(self, pending: dict[str, list[Any]], db: FakeDatabase):
        self._pending = pending
        self._db = db

    async def get(self, entity_id: uuid.UUID) -> FormTemplate | None:
        return self._db.templates.get(entity_id)

    async def add(self, entity: FormTemplate) -> FormTemplate:
        _stamp(entity)
        self._pending["templates"].append(entity)
        return entity

    async def delete(self, entity: FormTemplate) -> None:
        self._db.templates.pop(entity.id, None)

    async def add_version(self, version: FormTemplateVersion) -> FormTemplateVersion:
        _stamp(version)
        self._pending["versions"].append(version)
        return version

    async def get_for_update(self, template_id: uuid.UUID) -> FormTemplate | None:
        return self._db.templates.get(template_id)

    async def get_with_latest_version(self, template_id: uuid.UUID):
        template = self._db.templates.get(template_id)
        if template is None:
            return None
        return template, self._db.versions[(template_id, template.latest_version)]

    async def list_page(self, limit: int, after):
        rows = sorted(self._db.templates.values(), key=lambda t: (t.created_at, t.id), reverse=True)
        if after is not None:
            rows = [row for row in rows if (row.created_at, row.id) < after]
        return rows[:limit]

    async def get_version(self, template_id: uuid.UUID, version: int) -> FormTemplateVersion | None:
        return self._db.versions.get((template_id, version))


class FakeIdempotencyRepository:
    def __init__(self, pending: dict[str, list[Any]], db: FakeDatabase):
        self._pending = pending
        self._db = db

    async def get(self, entity_id: uuid.UUID) -> IdempotencyKey | None:
        return next((item for item in self._db.idempotency.values() if item.id == entity_id), None)

    async def add(self, entity: IdempotencyKey) -> IdempotencyKey:
        if (entity.idempotency_key, entity.scope) in self._db.idempotency:
            raise IdempotencyKeyTakenError()
        _stamp(entity)
        self._pending["idempotency"].append(entity)
        return entity

    async def delete(self, entity: IdempotencyKey) -> None:
        self._db.idempotency.pop((entity.idempotency_key, entity.scope), None)

    async def get_active(self, key: str, scope: str, now: datetime) -> IdempotencyKey | None:
        stored = self._db.idempotency.get((key, scope))
        return stored if stored and stored.expires_at > now else None

    async def delete_expired_key(self, key: str, scope: str, now: datetime) -> None:
        stored = self._db.idempotency.get((key, scope))
        if stored and stored.expires_at <= now:
            del self._db.idempotency[(key, scope)]

    async def delete_expired_batch(self, now: datetime, batch_size: int) -> int:
        expired = [pk for pk, item in self._db.idempotency.items() if item.expires_at <= now][:batch_size]
        for pk in expired:
            del self._db.idempotency[pk]
        return len(expired)


class FakeWorkerTasksRepository:
    def __init__(self, pending: dict[str, list[Any]], db: FakeDatabase):
        self._pending = pending
        self._db = db

    async def enqueue(self, task_type, payload, available_at, dedupe_key):
        task = {"id": uuid.uuid4(), "task_type": task_type, "payload": payload, "status": "pending",
                "available_at": available_at, "dedupe_key": dedupe_key}
        self._pending["worker_tasks"].append(("enqueue", task))
        return task["id"]

    async def claim_batch(self, batch_size, now, stale_before):
        return []

    async def mark_completed(self, task_id, now):
        self._pending["worker_tasks"].append(("completed", {"id": task_id}))

    async def mark_failed(self, task_id, error_message, retry_at, now):
        self._pending["worker_tasks"].append(
            ("failed", {"id": task_id, "error_message": error_message, "retry_at": retry_at})
        )


class FakeUnitOfWork:
    def __init__(self, db: FakeDatabase):
        self._db = db
        self._pending: dict[str, list[Any]] = {
            "imports": [],
            "templates": [],
            "versions": [],
            "idempotency": [],
            "worker_tasks": [],
        }
        self.imports = FakeImportsRepository(self._pending, db)
        self.templates = FakeTemplatesRepository(self._pending, db)
        self.idempotency = FakeIdempotencyRepository(self._pending, db)
        self.worker_tasks = FakeWorkerTasksRepository(self._pending, db)

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_: object) -> None:
        for items in self._pending.values():
            items.clear()

    async def commit(self) -> None:
        for entity in self._pending["imports"]:
            self._db.imports[entity.id] = entity
        for template in self._pending["templates"]:
            self._db.templates[template.id] = template
        for version in self._pending["versions"]:
            self._db.versions[(version.template_id, version.version)] = version
        for item in self._pending["idempotency"]:
            self._db.idempotency[(item.idempotency_key, item.scope)] = item
        for action, task in self._pending["worker_tasks"]:
            self._db.worker_tasks.append({"action": action, **task})
        for items in self._pending.values():
            items.clear()
        self._db.commits += 1
