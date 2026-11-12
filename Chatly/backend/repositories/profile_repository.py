"""Repositorio de perfiles y contactos del usuario.

Las tablas viven en `public` con RLS activa. Las escrituras y las lecturas de
perfil se hacen dentro de `actor_transaction`, que fija `app.current_user_id`.
La comprobación de alias usa `app.alias_exists`, función `SECURITY DEFINER` que
solo devuelve un booleano y no expone filas. La selección de intereses se
inserta en la misma transacción (ver `interest_repository`).

Los nombres de columnas están en español (AGENTS.md); las clases, funciones y
variables en inglés.
"""

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from Chatly.backend.core.errors import ConflictError, ErrorCode
from Chatly.backend.database.session import actor_transaction, get_app_session_factory
from Chatly.backend.repositories.interest_repository import get_interest_repository

_ALIAS_TAKEN_MESSAGE = "Ese alias ya está en uso. Elige otro."


@dataclass(frozen=True)
class ProfileData:
    """Datos públicos del perfil que la API devuelve en la sesión."""

    alias: str
    display_name: str


class ProfileRepository:
    """Acceso a `perfiles` y `contactos_usuario`."""

    async def alias_exists(self, alias: str) -> bool:
        """Indica si el alias ya está ocupado (comparación sin mayúsculas)."""
        async with get_app_session_factory()() as session:
            result = await session.execute(
                text("select app.alias_exists(:alias)"),
                {"alias": alias},
            )
            return bool(result.scalar())

    async def create_profile(
        self,
        *,
        user_id: str,
        alias: str,
        display_name: str,
        birth_date: date,
        gender: str,
        email: str,
        interest_ids: list[UUID] | None = None,
    ) -> None:
        """Crea el perfil, su contacto y su selección de intereses.

        Todo ocurre en la misma `actor_transaction`: si un interés no existe o
        ya no está activo, la transacción se revierte entera (no queda un
        perfil sin intereses coherente).
        """
        try:
            async with actor_transaction(UUID(user_id)) as session:
                await session.execute(
                    text(
                        "insert into public.perfiles"
                        " (id, alias, nombre_visible, fecha_nacimiento, genero)"
                        " values (:id, :alias, :nombre, :fecha, :genero)"
                    ),
                    {
                        "id": user_id,
                        "alias": alias,
                        "nombre": display_name,
                        "fecha": birth_date,
                        "genero": gender,
                    },
                )
                await session.execute(
                    text(
                        "insert into public.contactos_usuario"
                        " (usuario_id, correo_normalizado)"
                        " values (:id, :correo)"
                    ),
                    {"id": user_id, "correo": email.strip().lower()},
                )
                await get_interest_repository().insert_selection(
                    session, UUID(user_id), interest_ids or []
                )
        except IntegrityError as exc:
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", "") or ""
            if constraint == "uq_perfiles_alias":
                raise ConflictError(ErrorCode.ALIAS_TAKEN, _ALIAS_TAKEN_MESSAGE) from exc
            if constraint == "uq_contactos_correo":
                raise ConflictError(
                    ErrorCode.EMAIL_ALREADY_REGISTERED,
                    "Este correo ya está registrado. Inicia sesión o recupera tu contraseña.",
                ) from exc
            raise

    async def get_profile(self, user_id: str) -> ProfileData | None:
        """Perfil vigente del usuario, o `None` si aún no existe."""
        async with actor_transaction(UUID(user_id)) as session:
            row = (
                await session.execute(
                    text(
                        "select alias, nombre_visible from public.perfiles"
                        " where id = :id and eliminado_en is null"
                    ),
                    {"id": user_id},
                )
            ).first()
        if row is None:
            return None
        return ProfileData(alias=row[0], display_name=row[1])


@lru_cache
def get_profile_repository() -> ProfileRepository:
    """Instancia única del repositorio por proceso."""
    return ProfileRepository()
