"""Pruebas del envelope y handlers de error (`backend/core/errors.py`).

Se montan endpoints que lanzan cada tipo de error y se comprueba que la
respuesta respeta `{"error": {"code", "message", "details"?}}` con su código
HTTP, sin exponer trazas internas.
"""

from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from Chatly.backend.core.errors import (
    ConflictError,
    DomainError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    ValidationError,
    domain_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)


class _Cuerpo(BaseModel):
    """Modelo de prueba con un campo entero obligatorio."""

    edad: int


@contextmanager
def _client_api():
    """Cliente con los handlers registrados y endpoints de prueba.

    `raise_server_exceptions=False` deja que el handler de excepciones no
    controladas produzca su respuesta 500 sin lanzar el error al caller.
    """
    api_app = FastAPI()
    api_app.add_exception_handler(DomainError, domain_error_handler)
    api_app.add_exception_handler(RequestValidationError, validation_exception_handler)
    api_app.add_exception_handler(Exception, unhandled_exception_handler)

    @api_app.get("/validacion")
    async def _validacion() -> None:
        raise ValidationError("Alias demasiado corto.", details={"field": "alias"})

    @api_app.get("/no-autorizado")
    async def _no_autorizado() -> None:
        raise UnauthorizedError()

    @api_app.get("/prohibido")
    async def _prohibido() -> None:
        raise ForbiddenError()

    @api_app.get("/no-encontrado")
    async def _no_encontrado() -> None:
        raise NotFoundError()

    @api_app.get("/conflicto")
    async def _conflicto() -> None:
        raise ConflictError(ErrorCode.ALIAS_TAKEN)

    @api_app.get("/rate-limit")
    async def _rate_limit() -> None:
        raise RateLimitedError(retry_after=23)

    @api_app.post("/cuerpo")
    async def _cuerpo(cuerpo: _Cuerpo) -> None:
        return None

    @api_app.get("/inesperado")
    async def _inesperado() -> None:
        raise RuntimeError("detalle interno que no debe salir")

    with TestClient(api_app, raise_server_exceptions=False) as client:
        yield client


def test_envelope_error_dominio() -> None:
    """El error tipado devuelve el envelope con su código y estado."""
    with _client_api() as client:
        response = client.get("/conflicto")

    assert response.status_code == 409
    body = response.json()
    assert body == {
        "error": {
            "code": "alias_taken",
            "message": "La operación entra en conflicto con el estado actual.",
        }
    }


def _comprobar_status(ruta: str, status: int, code: str) -> None:
    with _client_api() as client:
        response = client.get(ruta)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_status_subclases() -> None:
    """Cada subclase de dominio mapea al código HTTP acordado."""
    _comprobar_status("/validacion", 422, "validation_error")
    _comprobar_status("/no-autorizado", 401, "unauthorized")
    _comprobar_status("/prohibido", 403, "forbidden")
    _comprobar_status("/no-encontrado", 404, "not_found")
    _comprobar_status("/conflicto", 409, "alias_taken")
    _comprobar_status("/rate-limit", 429, "rate_limited")


def test_rate_limit_incluye_retry_after() -> None:
    """429 incluye la cabecera `Retry-After` con los segundos definidos."""
    with _client_api() as client:
        response = client.get("/rate-limit")

    assert response.headers["retry-after"] == "23"


def test_validacion_request_devuelve_422_con_fields() -> None:
    """Pydantic inválido → 422 con `details.fields` y `details.field`."""
    with _client_api() as client:
        response = client.post("/cuerpo", json={"edad": "no-es-numero"})

    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]["field"] == "edad"
    fields = body["details"]["fields"]
    assert fields == [{"field": "edad", "message": fields[0]["message"]}]
    assert fields[0]["message"]


def test_excepcion_no_controlada_sin_traza() -> None:
    """500 con envelope genérico y sin detallar el error interno."""
    with _client_api() as client:
        response = client.get("/inesperado")

    assert response.status_code == 500
    texto = response.text
    # el detalle interno ("detalle interno que no debe salir") no se expone
    assert "detalle interno" not in texto.lower()
    assert "Traceback" not in texto
    assert response.json()["error"]["code"] == "internal_error"


def test_validation_error_subclase_default() -> None:
    """`ValidationError` de dominio usa el copy por defecto en español."""
    error = ValidationError()
    assert error.status_code == 422
    assert error.code == ErrorCode.VALIDATION_ERROR
