import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.database import DATABASE_UNAVAILABLE_ERRORS
from app.core.exceptions import ConflictError, DomainError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ConflictError: status.HTTP_409_CONFLICT,
}

HTTP_ERROR_MESSAGES: dict[int, tuple[str, str]] = {
    status.HTTP_404_NOT_FOUND: ("not_found", "No encontramos lo que buscas."),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("method_not_allowed", "Esta acción no está permitida."),
}


def error_body(code: str, message: str, details: list[dict] | None = None) -> dict:
    """Forma única de todos los errores que devuelve la API."""
    return {"error": {"code": code, "message": message, "details": details or []}}


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    status_code = STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    details = [{"code": d.code, "message": d.message, "field_id": d.field_id} for d in exc.details]
    return JSONResponse(status_code=status_code, content=error_body(exc.code, exc.message, details))


async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "code": err.get("type", "invalid"),
            "message": err.get("msg", "Valor inválido"),
            "field_id": ".".join(str(part) for part in err.get("loc", []) if part != "body") or None,
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_body("invalid_request", "Los datos enviados no son válidos.", details),
    )


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = HTTP_ERROR_MESSAGES.get(exc.status_code, ("http_error", str(exc.detail)))
    return JSONResponse(status_code=exc.status_code, content=error_body(code, message), headers=exc.headers)


async def database_unavailable_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("La base de datos no responde: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_body(
            "database_unavailable", "El servidor está ocupado en este momento. Intenta de nuevo en unos segundos."
        ),
    )


async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body("internal_error", "Ocurrió un error inesperado. Intenta de nuevo."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    for error_type in DATABASE_UNAVAILABLE_ERRORS:
        app.add_exception_handler(error_type, database_unavailable_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
