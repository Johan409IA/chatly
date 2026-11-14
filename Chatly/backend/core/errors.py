"""Errores de dominio y respuestas de error uniformes de la API.

El formato sigue `docs/api-contracts.md` §2:

    {"error": {"code": "...", "message": "...", "details": {...}}}

Los mensajes están en español, en segunda persona y sin detalles internos.
"""

import logging
from enum import StrEnum
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """Códigos de error acordados en el contrato de API."""

    VALIDATION_ERROR = "validation_error"
    WEAK_PASSWORD = "weak_password"
    UNAUTHORIZED = "unauthorized"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    EMAIL_ALREADY_REGISTERED = "email_already_registered"
    ALIAS_TAKEN = "alias_taken"
    ALIAS_CHANGE_TOO_SOON = "alias_change_too_soon"
    INVALID_CREDENTIALS = "invalid_credentials"
    ALREADY_MEMBER = "already_member"
    CONVERSATION_FULL = "conversation_full"
    NOT_MEMBER = "not_member"
    READ_ONLY_PERIOD = "read_only_period"
    POLL_LOCKED = "poll_locked"
    POLL_CLOSED = "poll_closed"
    POLL_HAS_VOTES = "poll_has_votes"
    MESSAGE_TOO_LONG = "message_too_long"
    INVALID_AVATAR = "invalid_avatar"
    INTEREST_LIMIT_EXCEEDED = "interest_limit_exceeded"
    DUPLICATE_REQUEST = "duplicate_request"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


class DomainError(Exception):
    """Error de negocio tipado: el handler lo traduce a una respuesta HTTP."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.headers = headers


class ValidationError(DomainError):
    def __init__(self, message: str = "Revisa los datos enviados.", **kwargs: Any) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, status_code=422, **kwargs)


class UnauthorizedError(DomainError):
    def __init__(self, message: str = "Inicia sesión para continuar.", **kwargs: Any) -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message, status_code=401, **kwargs)


class ForbiddenError(DomainError):
    def __init__(
        self,
        message: str = "No tienes permiso para realizar esta acción.",
        **kwargs: Any,
    ) -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, status_code=403, **kwargs)


class NotFoundError(DomainError):
    def __init__(self, message: str = "No encontramos lo que buscas.", **kwargs: Any) -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=404, **kwargs)


class ConflictError(DomainError):
    """Conflicto con el estado actual; el código concreto lo elige el servicio."""

    def __init__(
        self,
        code: ErrorCode,
        message: str = "La operación entra en conflicto con el estado actual.",
        **kwargs: Any,
    ) -> None:
        super().__init__(code, message, status_code=409, **kwargs)


class RateLimitedError(DomainError):
    def __init__(
        self,
        message: str = "Has hecho demasiadas solicitudes. Espera un momento.",
        *,
        retry_after: int = 60,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("headers", {"Retry-After": str(retry_after)})
        super().__init__(ErrorCode.RATE_LIMITED, message, status_code=429, **kwargs)


def _error_body(
    code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": str(code), "message": message}
    if details:
        error["details"] = details
    return {"error": error}


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Traduce un error de dominio al envelope uniforme."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, exc.details),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convierte errores de validación de Pydantic al envelope uniforme."""
    fields: list[dict[str, str | None]] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ()) if part != "body"]
        fields.append(
            {
                "field": ".".join(location) or None,
                "message": error.get("msg", "El valor no es válido."),
            }
        )

    details: dict[str, Any] = {"fields": fields}
    if len(fields) == 1 and fields[0]["field"]:
        details["field"] = fields[0]["field"]

    return JSONResponse(
        status_code=422,
        content=_error_body(
            ErrorCode.VALIDATION_ERROR,
            "Revisa los datos enviados.",
            details,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Evita exponer trazas internas; deja el detalle solo en el log."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=_error_body(
            ErrorCode.INTERNAL_ERROR,
            "Ocurrió un error inesperado. Inténtalo de nuevo.",
        ),
    )
