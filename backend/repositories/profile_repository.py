"""Repositorio de perfiles y contactos del usuario.

Las tablas viven en `public` con RLS activa. Las escrituras y las lecturas de
perfil se hacen dentro de `actor_transaction`, que fija `app.current_user_id`.
La comprobación de alias usa `app.alias_exists`, función `SECURITY DEFINER` que
solo devuelve un booleano y no expone filas. La selección de intereses se
inserta en la misma transacción (ver `interest_repository`).

Los nombres de columnas están en español (AGENTS.md); las clases, funciones y
variables en inglés.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Chatly.backend.core.errors import ConflictError, ErrorCode, NotFoundError
from Chatly.backend.database.session import actor_transaction, get_app_session_factory
from Chatly.backend.repositories.interest_repository import get_interest_repository
from Chatly.backend.schemas.profile import (
    InterestTagDTO,
    ProfileMeDTO,
    ProfileUpdateRequest,
    UserSearchResultDTO,
)

_ALIAS_TAKEN_MESSAGE = "Ese alias ya está en uso. Elige otro."
_ALIAS_COOLDOWN_MESSAGE = "Solo puedes cambiar tu alias una vez cada 30 días. Inténtalo más tarde."
_SEARCH_LIMIT = 20
ALIAS_CHANGE_COOLDOWN = timedelta(days=30)


def alias_is_changeable(
    alias_changed_at: datetime | None, *, reference: datetime | None = None
) -> bool:
    """Indica si el alias puede cambiarse: nunca cambiado o pasaron 30 días (Q107).

    Regla única del cooldown: la usan `ProfileMeDTO.can_change_alias` (GET
    `/api/me`) y la validación de `update_me`, para que no se desincronicen.
    """
    if alias_changed_at is None:
        return True
    now = reference or datetime.now(UTC)
    changed = alias_changed_at
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=UTC)
    return now - changed >= ALIAS_CHANGE_COOLDOWN


_COLUMN_BY_FIELD = {
    "alias": "alias",
    "display_name": "nombre_visible",
    "birth_date": "fecha_nacimiento",
    "gender": "genero",
    "is_public": "visibilidad_publica",
}


def _campos_a_actualizar(change: ProfileUpdateRequest) -> dict[str, object]:
    """Campos a escribir en `perfiles`, mapeados a nombres de columna.

    Un campo enviado como `null` equivale a no haberlo enviado: la regla de
    «al menos un campo» de §5.2 ya trata `None` como ausente, y dejarlo pasar
    rompería el `NOT NULL` de `visibilidad_publica` con un error sin traducir.
    """
    return {
        _COLUMN_BY_FIELD[field]: value
        for field, value in change.model_dump(exclude_unset=True).items()
        if value is not None
    }


def _jsonable(value: object) -> object:
    """Serializa lo que `jsonb` no admite de forma nativa."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


async def _registrar_auditoria(
    session: AsyncSession,
    *,
    accion: str,
    tipo_entidad: str,
    entidad_id: str,
    antes: dict[str, object] | None = None,
    despues: dict[str, object] | None = None,
) -> None:
    """Escribe el registro de auditoría dentro de la transacción abierta (Q43).

    `actor_id` sale del contexto RLS, no de un parámetro, para que la política
    `auditoria_insert_backend` valide contra el mismo actor que hace el cambio.
    La tabla no tiene claves foráneas a propósito; si la inserción falla, la
    transacción se revierte entera y no queda un cambio sin registro.
    """
    await session.execute(
        text(
            "insert into public.registros_auditoria"
            " (actor_id, accion, tipo_entidad, entidad_id, valores_anteriores,"
            " valores_nuevos)"
            " values (app.current_actor_id(), :accion, :tipo_entidad, :entidad_id,"
            " cast(:antes as jsonb), cast(:despues as jsonb))"
        ),
        {
            "accion": accion,
            "tipo_entidad": tipo_entidad,
            "entidad_id": entidad_id,
            "antes": json.dumps(antes, default=_jsonable) if antes else None,
            "despues": json.dumps(despues, default=_jsonable) if despues else None,
        },
    )


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

    async def get_me(self, user_id: str, email: str | None = None) -> ProfileMeDTO | None:
        """Perfil completo del propio usuario (§3.3), o `None` si no existe.

        Una sola consulta: la edad con `date_part('year', age(...))` y los
        intereses con el join `intereses_usuario → intereses →
        categorias_interes`, ordenados por el catálogo y alfabéticamente. El
        correo no viene de `contactos_usuario` (sin grant de lectura para
        `chatly_app`): lo aporta el JWT de la petición.
        """
        async with actor_transaction(UUID(user_id)) as session:
            rows = (
                await session.execute(
                    text(
                        "select p.id, p.alias, p.nombre_visible, p.ruta_avatar,"
                        " p.fecha_nacimiento, p.genero, p.alias_cambiado_en,"
                        " p.visibilidad_publica, p.creado_en,"
                        " (p.correo_verificado_en is not null) as correo_verificado,"
                        " date_part('year', age(now(), p.fecha_nacimiento))::int as edad,"
                        " i.id as interes_id, i.nombre as interes_nombre,"
                        " ci.nombre as categoria_nombre"
                        " from public.perfiles p"
                        " left join public.intereses_usuario iu on iu.usuario_id = p.id"
                        " left join public.intereses i on i.id = iu.interes_id and i.activo"
                        " left join public.categorias_interes ci on ci.id = i.categoria_id"
                        " where p.id = :id and p.eliminado_en is null"
                        " order by ci.orden nulls last, lower(i.nombre) nulls last"
                    ),
                    {"id": user_id},
                )
            ).all()
        if not rows:
            return None
        first = rows[0]
        interests = [
            InterestTagDTO(
                id=row.interes_id, name=row.interes_nombre, category=row.categoria_nombre
            )
            for row in rows
            if row.interes_id is not None
        ]
        return ProfileMeDTO(
            id=str(first.id),
            email=email or "",
            email_verified=bool(first.correo_verificado),
            alias=first.alias,
            display_name=first.nombre_visible,
            avatar_url=first.ruta_avatar,
            birth_date=first.fecha_nacimiento,
            age=int(first.edad),
            gender=first.genero,
            alias_changed_at=first.alias_cambiado_en,
            can_change_alias=alias_is_changeable(first.alias_cambiado_en),
            is_public=bool(first.visibilidad_publica),
            interests=interests,
            created_at=first.creado_en,
        )

    async def update_me(self, user_id: str, change: ProfileUpdateRequest) -> None:
        """Actualiza los campos presentes de `PATCH /api/me` (§5.2) y audita (Q43).

        El `select ... for update` sobre `perfiles` serializa cambios
        concurrentes del mismo usuario antes de validar el alias. Dos guardas,
        en este orden: el cooldown de 30 días (`alias_is_changeable`) y
        `app.alias_exists` (función `SECURITY DEFINER` de `0005a`); esta última
        es obligatoria aunque exista el índice único, para devolver
        `409 alias_taken` en vez de un `IntegrityError`.

        Solo se escriben las columnas cuyo valor cambia de verdad: reenviar el
        estado vigente no cuenta como cambio ni genera registro de auditoría.
        La auditoría va en la misma transacción, de modo que no exista un
        cambio sin registro.
        """
        updates = _campos_a_actualizar(change)
        if not updates:
            return
        async with actor_transaction(UUID(user_id)) as session:
            # Si el alias cambia hace falta conocer el cooldown vigente; si no,
            # basta con las columnas que se van a escribir.
            columnas = set(updates)
            if "alias" in updates:
                columnas |= {"alias", "alias_cambiado_en"}
            row = (
                await session.execute(
                    text(
                        f"select {', '.join(sorted(columnas))} from public.perfiles"
                        " where id = :id and eliminado_en is null for update"
                    ),
                    {"id": user_id},
                )
            ).first()
            if row is None:
                raise NotFoundError()
            if "alias" in updates and updates["alias"] != row.alias:
                if not alias_is_changeable(row.alias_cambiado_en):
                    raise ConflictError(ErrorCode.ALIAS_CHANGE_TOO_SOON, _ALIAS_COOLDOWN_MESSAGE)
                taken = (
                    await session.execute(
                        text("select app.alias_exists(:alias)"),
                        {"alias": updates["alias"]},
                    )
                ).scalar()
                if taken:
                    raise ConflictError(ErrorCode.ALIAS_TAKEN, _ALIAS_TAKEN_MESSAGE)
            cambios = {
                column: (getattr(row, column), value)
                for column, value in updates.items()
                if getattr(row, column) != value
            }
            if not cambios:
                return
            assignments = ", ".join(f"{column} = :{column}" for column in cambios)
            await session.execute(
                text(
                    f"update public.perfiles set {assignments}, actualizado_en = now()"
                    " where id = :id and eliminado_en is null"
                ),
                {**{column: nuevo for column, (_, nuevo) in cambios.items()}, "id": user_id},
            )
            await _registrar_auditoria(
                session,
                accion="perfil_actualizado",
                tipo_entidad="perfiles",
                entidad_id=user_id,
                antes={column: viejo for column, (viejo, _) in cambios.items()},
                despues={column: nuevo for column, (_, nuevo) in cambios.items()},
            )

    async def replace_interests(self, user_id: str, interest_ids: list[UUID]) -> None:
        """Reemplaza la selección completa de intereses (§16.2) y audita (Q43).

        El borrado y la inserción comparten la misma `actor_transaction`: si
        un interés no existe o ya no está activo, `insert_selection` lanza
        `ValidationError` y la transacción se revierte entera (no se pierde
        la selección anterior a medias).

        Reenviar la selección vigente no es un cambio, así que no genera
        registro de auditoría (Q43 evita registros de poco valor).
        """
        async with actor_transaction(UUID(user_id)) as session:
            seleccion_anterior = {
                row.interes_id
                for row in (
                    await session.execute(
                        text(
                            "select interes_id from public.intereses_usuario where usuario_id = :id"
                        ),
                        {"id": user_id},
                    )
                ).all()
            }
            await session.execute(
                text("delete from public.intereses_usuario where usuario_id = :id"),
                {"id": user_id},
            )
            await get_interest_repository().insert_selection(session, UUID(user_id), interest_ids)
            if seleccion_anterior != set(interest_ids):
                await _registrar_auditoria(
                    session,
                    accion="intereses_usuario_reemplazados",
                    tipo_entidad="intereses_usuario",
                    entidad_id=user_id,
                    antes={"interes_ids": sorted(str(i) for i in seleccion_anterior)},
                    despues={"interes_ids": [str(i) for i in interest_ids]},
                )

    async def search_users(
        self, actor_id: str, *, q: str | None = None, email: str | None = None
    ) -> list[UserSearchResultDTO]:
        """Búsqueda de usuarios (§6.1): parcial por alias o exacta por correo.

        Mutuamente excluyentes (lo valida la ruta); excluye al propio usuario
        y devuelve como máximo 20 resultados, nunca el correo. La búsqueda
        por correo usa `app.buscar_usuario_por_correo()` (de `0002`), que ya
        excluye al actor y solo expone campos públicos.
        """
        async with actor_transaction(UUID(actor_id)) as session:
            if email is not None:
                rows = (
                    await session.execute(
                        text(
                            "select usuario_id, alias, nombre_visible, ruta_avatar"
                            " from app.buscar_usuario_por_correo(:correo)"
                        ),
                        {"correo": email.strip().lower()},
                    )
                ).all()
            else:
                escaped = (q or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                rows = (
                    await session.execute(
                        text(
                            "select id, alias, nombre_visible, ruta_avatar from public.perfiles"
                            " where eliminado_en is null and id <> :actor_id"
                            " and alias ilike :patron"
                            " order by alias"
                            f" limit {_SEARCH_LIMIT}"
                        ),
                        {"actor_id": actor_id, "patron": f"%{escaped}%"},
                    )
                ).all()
        return [
            UserSearchResultDTO(
                id=str(row[0]), alias=row[1], display_name=row[2], avatar_url=row[3]
            )
            for row in rows
        ]

    async def is_verified(self, user_id: str) -> bool:
        """Indica si el correo del actor está confirmado (Q15).

        `correo_verificado_en` es un espejo de `auth.users.email_confirmed_at`
        que mantiene el trigger de `0008_auth_sync`. No se deduce del JWT: el
        token de Supabase no distingue una cuenta sin confirmar.
        """
        async with actor_transaction(UUID(user_id)) as session:
            result = await session.execute(
                text(
                    "select correo_verificado_en is not null from public.perfiles"
                    " where id = :id and eliminado_en is null"
                ),
                {"id": user_id},
            )
            return bool(result.scalar())


@lru_cache
def get_profile_repository() -> ProfileRepository:
    """Instancia única del repositorio por proceso."""
    return ProfileRepository()
