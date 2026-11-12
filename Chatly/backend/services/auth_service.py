"""Servicio de autenticación: casos de uso entre la API y Supabase Auth.

Orquesta las llamadas REST (integrations/supabase/auth_client.py) y verifica
el JWT localmente antes de exponerlo (identidad del actor SIEMPRE del token,
`docs/api-contracts.md` §13). Las respuestas de reenvío y recuperación son
«siempre OK» por contrato: nunca revelan si una cuenta existe.

Operaciones críticas de auditoría llegan con `audit_logs` (Iteración 8,
roadmap.md:385-386); los puntos donde se registrarán están marcados.
"""

import logging
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from Chatly.backend.core.errors import ConflictError, ErrorCode, ValidationError
from Chatly.backend.core.jwt import get_jwt_verifier
from Chatly.backend.core.settings import get_settings
from Chatly.backend.integrations.supabase.auth_client import (
    SupabaseAuthClient,
    get_supabase_auth_client,
)
from Chatly.backend.repositories.interest_repository import (
    InterestRepository,
    get_interest_repository,
)
from Chatly.backend.repositories.profile_repository import (
    ProfileRepository,
    get_profile_repository,
)
from Chatly.backend.schemas.auth import (
    AuthSessionData,
    ConfirmRequest,
    EmailRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    StatusResponse,
    session_data_from_supabase,
)

logger = logging.getLogger(__name__)


class AuthService:
    """Caso de uso de autenticación por correo y contraseña."""

    def __init__(
        self,
        client: SupabaseAuthClient,
        profiles: ProfileRepository | None = None,
        interests: InterestRepository | None = None,
    ) -> None:
        self._client = client
        self._profiles = profiles or get_profile_repository()
        self._interests = interests or get_interest_repository()

    async def register(self, request: RegisterRequest) -> RegisterResponse:
        """Crea la cuenta en Supabase Auth y persiste el perfil; no inicia sesión (Q15)."""
        if await self._profiles.alias_exists(request.alias):
            raise ConflictError(ErrorCode.ALIAS_TAKEN, "Ese alias ya está en uso. Elige otro.")

        # Los intereses se validan contra el catálogo antes de crear la cuenta:
        # si un ID no existe o ya no está activo, el alta se rechaza y no queda
        # un usuario huérfano en Supabase Auth.
        if request.interest_ids:
            await self._check_interests(request.interest_ids)

        settings = get_settings()
        confirm_url = f"{settings.frontend_url.rstrip('/')}/auth/confirm"
        user_id = await self._client.sign_up(
            request.email, request.password, redirect_to=confirm_url
        )
        if user_id:
            await self._profiles.create_profile(
                user_id=user_id,
                alias=request.alias,
                display_name=request.display_name,
                birth_date=request.birth_date,
                gender=request.gender,
                email=request.email,
                interest_ids=list(request.interest_ids),
            )
        else:
            logger.warning("Supabase no devolvió el id del usuario al registrarse")

        return RegisterResponse(
            user_id=user_id,
            status="verification_required",
            email=request.email,
        )

    async def _check_interests(self, interest_ids: list[UUID]) -> None:
        """Verifica que todos los IDs enviados existen y están activos."""
        active_ids = await self._interests.active_interest_ids()
        unknown = [interest_id for interest_id in interest_ids if interest_id not in active_ids]
        if unknown:
            raise ValidationError(
                "Alguno de los intereses seleccionados no existe o ya no está disponible."
            )

    async def login(self, request: LoginRequest) -> AuthSessionData:
        """Grant `password` de Supabase; devuelve tokens validados localmente."""
        body = await self._client.sign_in(request.email, request.password)
        auth_session = session_data_from_supabase(body, email_verified=self._email_verified(body))
        # Verificar firma/claims (iss, aud, exp) antes de confiar en el token.
        auth_session.user.id = str(get_jwt_verifier().verify(auth_session.access_token).id)
        profile = await self._profiles.get_profile(auth_session.user.id)
        if profile is not None:
            auth_session.user.alias = profile.alias
            auth_session.user.display_name = profile.display_name
        return auth_session

    async def refresh(self, refresh_token: str) -> AuthSessionData:
        """Rota el refresh token; el JWT nuevo se valida antes de entregarse."""
        body = await self._client.refresh_session(refresh_token)
        # En refresh el correo ya se verificó al iniciar sesión, así que
        # email_verified=True se hereda de esa validación anterior.
        auth_session = session_data_from_supabase(body, email_verified=True)
        auth_session.user.id = str(get_jwt_verifier().verify(auth_session.access_token).id)
        return auth_session

    async def logout(self, access_token: str) -> None:
        """Revoca la sesión en Supabase; las cookies las limpia la ruta."""
        await self._client.sign_out(access_token)

    async def resend(self, request: EmailRequest) -> StatusResponse:
        """Reenvío de confirmación: respuestas `202` ocultando su existencia (§4.5)."""
        try:
            await self._client.resend_signup(request.email)
        except Exception:
            # Nunca revela si el correo existe; el límite de frecuencia (§14)
            # se aplicará con middleware (traducción pendiente de decisión).
            logger.info("Reenvío de confirmación no resuelto en Supabase")
        return StatusResponse()

    async def recover(self, request: EmailRequest) -> StatusResponse:
        """Enlace de recuperación: `202` siempre, sin revelar cuentas (§4.6)."""
        try:
            await self._client.recover(request.email)
        except Exception:
            logger.info("Recuperación no resuelta en Supabase para el correo dado")
        return StatusResponse()

    async def reset_password(self, request: ResetPasswordRequest) -> None:
        """Nueva contraseña con el access token del enlace de recuperación."""
        await self._client.update_password(request.token, request.password)

    async def confirm(self, request: ConfirmRequest) -> None:
        """Intercambia el token del enlace de confirmación (§4.8).

        Soporta las dos plantillas de correo de Supabase: `token_hash`
        (recomendada) y `code` del flujo PKCE.
        """
        if request.token_hash:
            await self._client.verify_signup(request.token_hash, request.type)
        else:
            await self._client.exchange_code(request.code or "")

    @staticmethod
    def _email_verified(body: dict[str, object]) -> bool:
        user = body.get("user") or {}
        if not isinstance(user, dict):
            return False
        return bool(user.get("email_confirmed_at") or user.get("email_verified_at"))


@lru_cache
def get_auth_service() -> AuthService:
    """Dependencia FastAPI: instancia única del servicio por proceso."""
    return AuthService(get_supabase_auth_client(), get_profile_repository())


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
