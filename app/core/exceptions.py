from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDetail:
    code: str
    message: str
    field_id: str | None = None


class DomainError(Exception):
    """Error base del dominio. Los services lanzan estos, nunca HTTPException."""

    default_code = "domain_error"

    def __init__(self, message: str, code: str | None = None, details: list[ErrorDetail] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details or []


class NotFoundError(DomainError):
    default_code = "not_found"


class ValidationError(DomainError):
    default_code = "validation_error"


class ConflictError(DomainError):
    default_code = "conflict"
