from enum import StrEnum


class WorkerTaskType(StrEnum):
    EXTRACT_IMPORT = "extract_import"
    PURGE_EXPIRED_IDEMPOTENCY_KEYS = "purge_expired_idempotency_keys"
    DELETE_STORAGE_OBJECT = "delete_storage_object"
