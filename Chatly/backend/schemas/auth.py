"""Modelos Pydantic de los endpoints de autenticación (`docs/api-contracts.md` §4).

Las reglas de campo replican las validaciones de cliente de
`Chatly/state/auth_state.py`: la validación definitiva vive aquí (servidor).

Errores:
- Reglas de formato → 422 `validation_error` (handler de Pydantic).
- Política de contraseñas y edad fuera de rango → 422 con el código
  específico (`weak_password`); se lanza `DomainError` y Pydantic no lo
  envuelve porque no es `ValueError`.
"""

import re
from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Chatly.backend.core.errors import DomainError, ErrorCode

_ALIAS_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_EMAIL_MESSAGE = "Escribe un correo válido."
_ALIAS_MESSAGE = "El alias debe tener 3–20 caracteres: letra inicial y luego letras, números o _."
_NAME_MESSAGE = "El nombre debe tener entre 2 y 60 caracteres."
_AGE_MESSAGE = "Debes tener entre 18 y 120 años."
_PASSWORD_MESSAGE = (
    "La contraseña debe tener al menos 8 caracteres e incluir una mayúscula, "
    "una minúscula y un carácter especial."
)

_MIN_AGE = 18
_MAX_AGE = 120

# Máximo de intereses personales por usuario (Q124). El catálogo completo vive
# en `docs/api-contracts.md` §4.1 y §16.2.
MAX_INTERESTS = 10


def email_is_valid(value: str) -> bool:
    """Formato básico de correo acordado en el contrato (§4.1)."""
    return bool(_EMAIL_RE.fullmatch(value))


def password_is_strong(value: str) -> bool:
    """Mínimo 8, una mayúscula, una minúscula y un símbolo; el número es opcional."""
    if len(value) < 8:
        return False
    has_upper = any(character.isupper() for character in value)
    has_lower = any(character.islower() for character in value)
    has_symbol = any(not character.isalnum() for character in value)
    return has_upper and has_lower and has_symbol


class LoginRequest(BaseModel):
    """Cuerpo de `POST /api/auth/login` (§4.2)."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_RE.fullmatch(normalized):
            raise ValueError(_EMAIL_MESSAGE)
        return normalized

    @field_validator("password")
    @classmethod
    def _password_present(cls, value: str) -> str:
        if not value:
            raise ValueError("Escribe tu contraseña.")
        return value


class RegisterRequest(BaseModel):
    """Cuerpo de `POST /api/auth/register` (§4.1); todo obligatorio (Q109–Q111).

    `interest_ids` es opcional (Q117, Q178): entre 0 y 10 IDs del catálogo.
    """

    email: str
    password: str
    alias: str
    display_name: str
    birth_date: date
    gender: Literal["femenino", "masculino"]
    interest_ids: list[UUID] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_RE.fullmatch(normalized):
            raise ValueError(_EMAIL_MESSAGE)
        return normalized

    @field_validator("interest_ids")
    @classmethod
    def _check_interest_ids(cls, value: list[UUID]) -> list[UUID]:
        """Sin duplicados y como mucho 10 intereses (§4.1)."""
        if len(set(value)) != len(value):
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                "No repitas intereses en la selección.",
                status_code=422,
            )
        if len(value) > MAX_INTERESTS:
            raise DomainError(
                ErrorCode.INTEREST_LIMIT_EXCEEDED,
                f"Puedes elegir hasta {MAX_INTERESTS} intereses.",
                status_code=422,
            )
        return value

    @field_validator("alias")
    @classmethod
    def _normalize_alias(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _ALIAS_RE.fullmatch(normalized):
            raise ValueError(_ALIAS_MESSAGE)
        return normalized

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not 2 <= len(name) <= 60:
            raise ValueError(_NAME_MESSAGE)
        return name

    @field_validator("birth_date")
    @classmethod
    def _check_birth_date(cls, value: date) -> date:
        if value > date.today() or value < date(1900, 1, 1):
            raise ValueError(_AGE_MESSAGE)
        return value

    @model_validator(mode="after")
    def _check_rules(self) -> "RegisterRequest":
        today = date.today()
        age_years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age_years -= 1
        if not _MIN_AGE <= age_years <= _MAX_AGE:
            raise DomainError(ErrorCode.VALIDATION_ERROR, _AGE_MESSAGE, status_code=422)
        if not password_is_strong(self.password):
            raise DomainError(ErrorCode.WEAK_PASSWORD, _PASSWORD_MESSAGE, status_code=422)
        return self


class EmailRequest(BaseModel):
    """Cuerpo de reenvío y recuperación (§4.5, §4.6)."""

    email: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_RE.fullmatch(normalized):
            raise ValueError(_EMAIL_MESSAGE)
        return normalized


class ResetPasswordRequest(BaseModel):
    """Cuerpo de `POST /api/auth/reset-password` (§4.7).

    `token_hash` es el que trae el enlace de la plantilla `{{ .TokenHash }}`;
    el servicio lo canjea por una sesión de recuperación antes de cambiar la
    contraseña.
    """

    token_hash: str
    password: str

    @field_validator("token_hash")
    @classmethod
    def _token_hash_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El enlace de recuperación no es válido.")
        return value.strip()

    @model_validator(mode="after")
    def _check_password(self) -> "ResetPasswordRequest":
        if not password_is_strong(self.password):
            raise DomainError(ErrorCode.WEAK_PASSWORD, _PASSWORD_MESSAGE, status_code=422)
        return self


class ConfirmRequest(BaseModel):
    """Cuerpo de `POST /api/auth/confirm` (§4.8 acordada el 2026-11-04).

    Acepta el `token_hash` de la plantilla `{{ .TokenHash }}` o el `code` del
    flujo PKCE, para que la confirmación funcione con cualquiera de las dos
    configuraciones de correo de Supabase.
    """

    code: str | None = None
    token_hash: str | None = None
    type: Literal["signup", "invite", "magiclink", "recovery", "email_change"] = "signup"

    @model_validator(mode="after")
    def _one_token_present(self) -> "ConfirmRequest":
        code = (self.code or "").strip()
        token_hash = (self.token_hash or "").strip()
        if not code and not token_hash:
            raise ValueError("El enlace de confirmación no es válido.")
        self.code = code or None
        self.token_hash = token_hash or None
        return self


class UserProfileDTO(BaseModel):
    """Datos visibles del usuario autenticado (§4.2)."""

    id: str
    # alias y display_name llegan con `profiles`; hasta entonces quedan nulos
    # (roadmap.md:173-177) la interfaz ya los muestra como opcionales.
    alias: str | None = None
    display_name: str | None = None
    email_verified: bool


class RegisterResponse(BaseModel):
    """Respuesta de registro (§4.1): siempre `verification_required` (Q15)."""

    user_id: str
    status: Literal["verification_required"]
    email: str


class AuthSessionResponse(BaseModel):
    """Respuesta pública de login/refresh (§4.2); el refresh vive en la cookie."""

    access_token: str
    expires_in: int
    user: UserProfileDTO


class AuthSessionData(AuthSessionResponse):
    """Interno: añade el refresh_token que las cookies llevan al navegador."""

    refresh_token: str


class StatusResponse(BaseModel):
    """Respuesta `202` de reenvío y recuperación (siempre, sin revelar cuentas)."""

    status: Literal["sent"] = "sent"


def session_data_from_supabase(body: dict[str, Any], *, email_verified: bool) -> AuthSessionData:
    """Normaliza la respuesta de grants de Supabase a `AuthSessionData`.

    `email_verified` lo calcula el servicio: en login con `email_confirmed_at`
    del usuario; en refresh se hereda porque ya se validó al iniciar sesión.
    """
    user = body.get("user") or {}
    return AuthSessionData(
        access_token=str(body["access_token"]),
        refresh_token=str(body["refresh_token"]),
        expires_in=int(body.get("expires_in", 600)),
        user=UserProfileDTO(
            id=str(user.get("id", "")),
            email_verified=email_verified,
        ),
    )
