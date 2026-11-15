"""Modelos Pydantic de los endpoints de perfil propio (`docs/api-contracts.md` §5, §6.1, §16.2).

Las reglas de campo replican las de `schemas/auth.py`: los mensajes y límites
(`_ALIAS_RE`, `_ALIAS_MESSAGE`, `_NAME_MESSAGE`, `_AGE_MESSAGE`, `_MIN_AGE`,
`_MAX_AGE`, `MAX_INTERESTS`) se reutilizan, no se duplican.

Errores:
- Reglas de formato → 422 `validation_error` (handler de Pydantic).
- «Al menos un campo» en `PATCH /api/me` y el límite de intereses → 422 con
  el código específico; se lanza `DomainError` y Pydantic no lo envuelve
  porque no es `ValueError`.
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from Chatly.backend.core.errors import DomainError, ErrorCode
from Chatly.backend.schemas.auth import (
    _AGE_MESSAGE,
    _ALIAS_MESSAGE,
    _ALIAS_RE,
    _MAX_AGE,
    _MIN_AGE,
    _NAME_MESSAGE,
    MAX_INTERESTS,
)


class InterestTagDTO(BaseModel):
    """Un interés del perfil con su categoría (§3.3 `ProfileMe.interests`)."""

    id: UUID
    name: str
    category: str


class ProfileMeDTO(BaseModel):
    """Perfil propio con todos los campos del contrato (§3.3).

    `age` se calcula en la consulta (`date_part('year', age(...))`); la fecha
    de nacimiento sí se incluye porque es el propio perfil. `can_change_alias`
    refleja el cooldown de 30 días del alias (Q107).
    """

    id: str
    email: str
    email_verified: bool
    alias: str
    display_name: str
    avatar_url: str | None = None
    birth_date: date
    age: int
    gender: str
    alias_changed_at: datetime | None = None
    can_change_alias: bool
    is_public: bool
    interests: list[InterestTagDTO] = Field(default_factory=list)
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    """Cuerpo de `PATCH /api/me` (§5.2): todo opcional, pero al menos un campo."""

    display_name: str | None = None
    alias: str | None = None
    birth_date: date | None = None
    gender: Literal["femenino", "masculino"] | None = None
    is_public: bool | None = None

    @field_validator("alias")
    @classmethod
    def _normalize_alias(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _ALIAS_RE.fullmatch(normalized):
            raise ValueError(_ALIAS_MESSAGE)
        return normalized

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        name = " ".join(value.split())
        if not 2 <= len(name) <= 60:
            raise ValueError(_NAME_MESSAGE)
        return name

    @field_validator("birth_date")
    @classmethod
    def _check_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        if value > date.today() or value < date(1900, 1, 1):
            raise ValueError(_AGE_MESSAGE)
        return value

    @model_validator(mode="after")
    def _check_rules(self) -> "ProfileUpdateRequest":
        if (
            self.display_name is None
            and self.alias is None
            and self.birth_date is None
            and self.gender is None
            and self.is_public is None
        ):
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                "Indica al menos un campo para actualizar.",
                status_code=422,
            )
        if self.birth_date is not None:
            today = date.today()
            age_years = today.year - self.birth_date.year
            if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
                age_years -= 1
            if not _MIN_AGE <= age_years <= _MAX_AGE:
                raise DomainError(ErrorCode.VALIDATION_ERROR, _AGE_MESSAGE, status_code=422)
        return self


class InterestsUpdateRequest(BaseModel):
    """Cuerpo de `PUT /api/me/interests` (§16.2): reemplazo completo, 0–10."""

    interest_ids: list[UUID] = Field(default_factory=list)

    @field_validator("interest_ids")
    @classmethod
    def _check_interest_ids(cls, value: list[UUID]) -> list[UUID]:
        """Sin duplicados y como mucho 10 intereses (Q117, Q124)."""
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


class UserSearchResultDTO(BaseModel):
    """Un resultado de `GET /api/users/search` (§6.1): nunca incluye el correo."""

    id: str
    alias: str
    display_name: str
    avatar_url: str | None = None


class UserSearchResponse(BaseModel):
    """Respuesta de búsqueda de usuarios (§6.1): máximo 20 resultados."""

    results: list[UserSearchResultDTO] = Field(default_factory=list)
