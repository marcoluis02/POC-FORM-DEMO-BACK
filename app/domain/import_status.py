from enum import StrEnum


class ImportStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"
