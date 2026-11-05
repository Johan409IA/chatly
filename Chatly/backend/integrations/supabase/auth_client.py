"""Cliente REST de Supabase Auth v2 para el backend.

Solo usa la clave publishable: el backend actúa como un cliente del SDK de
Supabase con las políticas de correo y confirmación configuradas en el
proyecto (`docs/architecture.md` §5). No se exponen operaciones administrativas.

Los errores se traducen a `DomainError` con los códigos del contrato
(`docs/api-contracts.md` §2/§4). NUNCA se registran payloads con credenciales
en los logs (`docs/api-contracts.md` §13).
"""

import logging
from functools import lru_cache
from typing import Any

import httpx

from Chatly.backend.core.errors import (
    DomainError,
    ErrorCode,
    RateLimitedError,
    UnauthorizedError,
)
from Chatly.backend.core.settings import get_settings

logger = logging.getLogger(__name__)

_INTERNAL_MESSAGE = "Ocurrió un error inesperado. Inténtalo de nuevo."
_CONECTION_MESSAGE = "No hay conexión con el servicio de cuentas. Inténtalo de nuevo."

# Traducción de `error_code` de Supabase Auth al contrato de Chatly.
_ERROR_MAP = {
    "user_already_exists": (
        ErrorCode.EMAIL_ALREADY_REGISTERED,
        409,
        "Este correo ya está registrado. Inicia sesión o recupera tu contraseña.",
    ),
    "email_exists": (
        ErrorCode.EMAIL_ALREADY_REGISTERED,
        409,
        "Este correo ya está registrado. Inicia sesión o recupera tu contraseña.",
    ),
    "invalid_credentials": (
        ErrorCode.INVALID_CREDENTIALS,
        401,
        "Correo o contraseña incorrectos.",
    ),
    "email_not_confirmed": (
        ErrorCode.EMAIL_NOT_VERIFIED,
        403,
        "Confirma tu correo para poder entrar.",
    ),
    "weak_password": (
        ErrorCode.WEAK_PASSWORD,
        422,
        "La contraseña debe tener al menos 8 caracteres e incluir una mayúscula, "
        "una minúscula y un carácter especial.",
    ),
    "over_email_send_rate_limit": (
        ErrorCode.RATE_LIMITED,
        429,
        "Demasiados intentos de envío. Espera unos minutos.",
    ),
    "same_password": (
        ErrorCode.WEAK_PASSWORD,
        422,
        "La nueva contraseña debe ser distinta de la anterior.",
    ),
    "refresh_token_not_found": (
        ErrorCode.UNAUTHORIZED,
        401,
        "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo.",
    ),
}


def _translate_status_error(exc: httpx.HTTPStatusError) -> DomainError:
    """Convierte un error HTTP de Supabase Auth en un `DomainError` del contrato."""
    try:
        body: dict[str, Any] = exc.response.json()
    except Exception:
        body = {}
    code = str(body.get("error_code") or body.get("error") or "")
    message = str(body.get("msg", "")) or None

    mapped = _ERROR_MAP.get(code)
    if mapped is not None:
        error_code, status, default_message = mapped
        # Los textos de Supabase vienen en inglés: el contrato exige español.
        return DomainError(error_code, default_message, status_code=status)

    if exc.response.status_code == 429:
        return RateLimitedError()
    if exc.response.status_code == 401:
        return UnauthorizedError()
    if exc.response.status_code == 403:
        return DomainError(
            ErrorCode.FORBIDDEN,
            message or "No tienes permiso para realizar esta acción.",
            status_code=403,
        )
    if 400 <= exc.response.status_code < 500:
        return DomainError(
            ErrorCode.VALIDATION_ERROR,
            message or "Revisa los datos enviados.",
            status_code=exc.response.status_code,
        )
    logger.warning(
        "Supabase Auth respondió %s en %s", exc.response.status_code, exc.request.url.path
    )
    return DomainError(ErrorCode.INTERNAL_ERROR, _INTERNAL_MESSAGE, status_code=500)


class SupabaseAuthClient:
    """Envoltura httpx sobre los endpoints REST de Supabase Auth v2.

    Se crea una sola instancia por proceso con `get_supabase_auth_client()`.
    En pruebas se inyecta un `transport` propio (por ejemplo `httpx.MockTransport`).
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.supabase_url).rstrip("/")
        key = api_key or settings.supabase_publishable_key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(15.0),
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "User-Agent": "chatly-backend/1.0",
            },
            transport=transport,
            follow_redirects=False,
        )

    async def sign_up(self, email: str, password: str, redirect_to: str | None = None) -> str:
        """Crea la cuenta; devuelve el id del usuario en Supabase Auth.

        `redirect_to` hace que el enlace del correo aterrice en `/auth/confirm`
        (debe estar en las Redirect URLs permitidas del proyecto).
        """
        body = await self._request(
            "POST",
            "/auth/v1/signup",
            json={"email": email, "password": password},
            params={"redirect_to": redirect_to} if redirect_to else None,
        )
        user = body.get("user")
        user_id = user.get("id") if isinstance(user, dict) else None
        return str(body.get("id") or user_id or "")

    async def sign_in(self, email: str, password: str) -> dict[str, Any]:
        """Grant `password`: devuelve access_token, refresh_token, expires_in y user."""
        return await self._request(
            "POST",
            "/auth/v1/token",
            json={"email": email, "password": password},
            params={"grant_type": "password"},
        )

    async def refresh_session(self, refresh_token: str) -> dict[str, Any]:
        """Grant `refresh_token`: rota el refresh y devuelve tokens nuevos."""
        return await self._request(
            "POST",
            "/auth/v1/token",
            json={"refresh_token": refresh_token},
            params={"grant_type": "refresh_token"},
        )

    async def sign_out(self, access_token: str) -> None:
        """Revoca la sesión de Supabase asociada al refresh token del usuario."""
        await self._request(
            "POST",
            "/auth/v1/logout",
            extra_headers={"Authorization": f"Bearer {access_token}"},
            expected_status=204,
        )

    async def resend_signup(self, email: str) -> None:
        """Reenvía el correo de confirmación de registro."""
        await self._request("POST", "/auth/v1/resend", json={"type": "signup", "email": email})

    async def recover(self, email: str) -> None:
        """Envía el enlace de recuperación de contraseña."""
        await self._request("POST", "/auth/v1/recover", json={"email": email})

    async def update_password(self, token: str, password: str) -> None:
        """Cambia la contraseña con el access token del enlace de recuperación."""
        await self._request(
            "PUT",
            "/auth/v1/user",
            json={"password": password},
            extra_headers={"Authorization": f"Bearer {token}"},
        )

    async def verify_signup(self, token_hash: str, verify_type: str = "signup") -> dict[str, Any]:
        """Confirma el correo con el `token_hash` del enlace (grant de flujo de email).

        Es el flujo de la plantilla que usa `{{ .TokenHash }}`. Si la plantilla
        de Supabase usa PKCE, el enlace trae `?code=` y se usa `exchange_code`.
        """
        return await self._request(
            "POST",
            "/auth/v1/verify",
            json={"type": verify_type, "token_hash": token_hash},
        )

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """Intercambia el `code` PKCE del enlace de confirmación por una sesión."""
        return await self._request(
            "POST",
            "/auth/v1/token",
            json={"auth_code": code},
            params={"grant_type": "pkce"},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> dict[str, Any]:
        """Petición única con traducción de errores al contrato.

        Devuelve el cuerpo JSON cuando lo hay; `expected_status` distingue
        204 (sin cuerpo) del resto.
        """
        try:
            response = await self._client.request(
                method, path, json=json, params=params, headers=extra_headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise _translate_status_error(exc) from None
        except httpx.HTTPError:
            logger.warning("Supabase Auth no disponible en %s %s", method, path)
            raise DomainError(
                ErrorCode.INTERNAL_ERROR, _CONECTION_MESSAGE, status_code=503
            ) from None

        if response.status_code == expected_status == 204 or not response.content:
            return {}
        try:
            body: dict[str, Any] = response.json()
        except Exception as exc:
            logger.warning("Respuesta no JSON de Supabase Auth en %s", path)
            raise DomainError(ErrorCode.INTERNAL_ERROR, _INTERNAL_MESSAGE, status_code=500) from exc
        return body if isinstance(body, dict) else {}


@lru_cache
def get_supabase_auth_client() -> SupabaseAuthClient:
    """Instancia única del cliente de Supabase Auth para el proceso."""
    return SupabaseAuthClient()
