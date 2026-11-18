"""Dependencias de autenticación para los endpoints de la API.

Sigue `docs/architecture.md` §4.2: `Request → verify_jwt (Depends) → ...`.
El token llega por la cookie `chatly_at` (HttpOnly) o, solo en pruebas,
por `Authorization: Bearer <jwt>`. La identidad siempre sale del JWT.

La verificación de correo **no** se evalúa en RLS: las políticas solo ven
`app.current_user_id`, así que la regla vive aquí, en una consulta a
`perfiles.correo_verificado_en` (`docs/authorization-matrix.md` §2.1).
RLS gobierna membresía y periodo; la API gobierna la verificación.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import Depends, Request

from Chatly.backend.core.errors import DomainError, ErrorCode, UnauthorizedError
from Chatly.backend.core.jwt import Actor, get_jwt_verifier
from Chatly.backend.repositories.conversation_repository import (
    ConversationRepository,
    get_conversation_repository,
)
from Chatly.backend.repositories.profile_repository import (
    ProfileRepository,
    get_profile_repository,
)

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


def get_profile_repository_dep() -> ProfileRepository:
    """Dependencia FastAPI: repositorio de perfiles (sustituible en pruebas)."""
    return get_profile_repository()


ProfileRepositoryDep = Annotated[ProfileRepository, Depends(get_profile_repository_dep)]


async def require_verified_actor(
    actor: Annotated[Actor, Depends(require_actor)],
    profiles: ProfileRepositoryDep,
) -> Actor:
    """Actor con el correo confirmado; `403 email_not_verified` si no lo está (Q15)."""
    if not await profiles.is_verified(str(actor.id)):
        raise DomainError(
            ErrorCode.EMAIL_NOT_VERIFIED,
            "Confirma tu correo para usar el chat.",
            status_code=403,
        )
    return actor


VerifiedActor = Annotated[Actor, Depends(require_verified_actor)]


def get_conversation_repository_dep() -> ConversationRepository:
    """Dependencia FastAPI: repositorio de conversaciones (sustituible en pruebas)."""
    return get_conversation_repository()


ConversationRepositoryDep = Annotated[
    ConversationRepository, Depends(get_conversation_repository_dep)
]