"""Endpoints de autenticación (docs/api-contracts.md §4 y §4.8 acordada).

Contrato de sesión:
- El backend fija `chatly_at` (access, HttpOnly) y `chatly_rt` (refresh,
  HttpOnly) con `Secure` en producción y `SameSite=Lax` (§4.2).
- `access_token` vuelve en el cuerpo solo para el Realtime del frontend;
  se guarda en memoria, nunca en cookies accesibles por JS.

Rutas públicas (sin sesión): register, login, refresh, resend, recover,
reset-password y confirm. `logout` exige usuario de sessión.
"""

from fastapi import APIRouter, Request, Response

from Chatly.backend.core.errors import UnauthorizedError
from Chatly.backend.core.settings import get_settings
from Chatly.backend.schemas.auth import (
    AuthSessionResponse,
    ConfirmRequest,
    EmailRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    StatusResponse,
)
from Chatly.backend.services.auth_service import AuthServiceDep

router = APIRouter(tags=["auth"])

ACCESS_COOKIE = "chatly_at"
REFRESH_COOKIE = "chatly_rt"

# Supabase no expira los refresh tokens (salvo periodo de reutilización); la
# cookie vive 30 días como decisión local, revisable con el frontend.
_REFRESH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def _cookie_secure() -> bool:
    """`Secure` solo en producción: en dev la app corre sobre http://localhost."""
    return get_settings().app_env == "production"


def _set_session_cookies(
    response: Response, access_token: str, refresh_token: str, expires_in: int
) -> None:
    """Fija ambas cookies de sesión httpOnly (§4.2)."""
    for name, value, max_age in (
        (ACCESS_COOKIE, access_token, expires_in),
        (REFRESH_COOKIE, refresh_token, _REFRESH_COOKIE_MAX_AGE),
    ):
        response.set_cookie(
            key=name,
            value=value,
            max_age=max_age,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            path="/",
        )


def _clear_session_cookies(response: Response) -> None:
    """Elimina ambas cookies de sesión."""
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(key=name, path="/")


@router.post("/api/auth/register", status_code=201)
async def register(
    request: RegisterRequest,
    service: AuthServiceDep,
) -> RegisterResponse:
    """Crea la cuenta; la interfaz termina en «verificación pendiente» (Q15).

    TODO: límites de frecuencia del contrato §14 aún sin middleware.
    """
    return await service.register(request)


@router.post("/api/auth/login")
async def login(
    request: LoginRequest,
    response: Response,
    service: AuthServiceDep,
) -> AuthSessionResponse:
    """Inicia sesión y fija las cookies HttpOnly de la API (§4.2)."""
    session = await service.login(request)
    _set_session_cookies(response, session.access_token, session.refresh_token, session.expires_in)
    return session


@router.post("/api/auth/refresh")
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> AuthSessionResponse:
    """Rota el refresh de la cookie y devuelve el access token renovado (§4.3)."""
    refresh_token = request.cookies.get(REFRESH_COOKIE, "")
    if not refresh_token:
        raise UnauthorizedError("Tu sesión no es válida o ha expirado. Inicia sesión de nuevo.")
    session = await service.refresh(refresh_token)
    _set_session_cookies(response, session.access_token, session.refresh_token, session.expires_in)
    return session


@router.post("/api/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    service: AuthServiceDep,
) -> None:
    """Revoca la sesión en Supabase y limpia cookies (§4.4)."""
    refresh_token = request.cookies.get(REFRESH_COOKIE, "")
    if not refresh_token:
        raise UnauthorizedError("No hay una sesión activa para cerrar.")
    # La revocación necesita el access token de la cookie `chatly_at`.
    access_token = request.cookies.get(ACCESS_COOKIE, "")
    await service.logout(access_token)
    _clear_session_cookies(response)


@router.post("/api/auth/resend-verification", status_code=202)
async def resend_verification(
    request: EmailRequest,
    service: AuthServiceDep,
) -> StatusResponse:
    """`202` siempre: no revela si el correo existe (§4.5).

    TODO: límite 3 cada 15 minutos por IP y correo (§14) con middleware.
    """
    return await service.resend(request)


@router.post("/api/auth/forgot-password", status_code=202)
async def forgot_password(
    request: EmailRequest,
    service: AuthServiceDep,
) -> StatusResponse:
    """`202` siempre; el correo lleva el enlace de Supabase (§4.6)."""
    return await service.recover(request)


@router.post("/api/auth/reset-password", status_code=204)
async def reset_password(
    request: ResetPasswordRequest,
    service: AuthServiceDep,
) -> None:
    """Nueva contraseña con el `token_hash` del enlace de recuperación (§4.7)."""
    await service.reset_password(request)


@router.post("/api/auth/confirm", status_code=204)
async def confirm(
    request: ConfirmRequest,
    service: AuthServiceDep,
) -> None:
    """Intercambia el código del enlace de confirmación de registro (§4.8)."""
    await service.confirm(request)
