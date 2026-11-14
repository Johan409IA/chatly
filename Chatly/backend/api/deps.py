"""Dependencias de autenticación para los endpoints de la API.

Sigue `docs/architecture.md` §4.2: `Request → verify_jwt (Depends) → ...`.
El token llega por la cookie `chatly_at` (HttpOnly) o, solo en pruebas,
por `Authorization: Bearer <jwt>`. La identidad siempre sale del JWT.
"""

import asyncio
import logging

from fastapi import Request

from Chatly.backend.core.errors import UnauthorizedError
from Chatly.backend.core.jwt import Actor, get_jwt_verifier

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "chatly_at"


def _extract_token(request: Request) -> str | None:
    """Obtiene el token de la cabecera Authorization o de la cookie."""
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return request.cookies.get(ACCESS_TOKEN_COOKIE)


async def require_actor(request: Request) -> Actor:
    """Verifica el JWT y devuelve el actor; 401 con envelope si es inválido."""
    token = _extract_token(request)
    if not token:
        raise UnauthorizedError()

    try:
        # La descarga del JWKS es I/O síncrona: se hace en un hilo para no
        # bloquear el event loop cuando la caché de claves expira.
        return await asyncio.to_thread(get_jwt_verifier().verify, token)
    except Exception:
        logger.warning("JWT inválido o expirado en %s", request.url.path)
        raise UnauthorizedError(
            "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."
        ) from None
