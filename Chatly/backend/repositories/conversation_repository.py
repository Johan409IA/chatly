"""Repositorio de conversaciones del chat directo 1:1.

Las tablas viven en `public` con RLS activa. Todas las consultas se hacen dentro
de `actor_transaction`, que fija `app.current_user_id`. Los nombres de columnas
están en español (AGENTS.md); las clases, funciones y variables en inglés.
"""

from functools import lru_cache
from uuid import UUID

from sqlalchemy import text

from Chatly.backend.database.session import actor_transaction
from Chatly.backend.schemas.chat import ConversationList, ConversationSummary

_PREVIEW_LENGTH = 80
_DELETED_PREVIEW = "Se eliminó un mensaje"
_POLL_PREVIEW = "Encuesta"

# Conversaciones donde el actor tiene una membresía activa (§7.1). El nombre y
# el avatar de un chat directo son los de la otra persona. `no_leidos` cuenta
# también los mensajes de sistema (autor nulo) gracias a `is distinct from`.
_LIST_CONVERSATIONS_SQL = text(
    """
    select
        c.id,
        c.tipo,
        case when c.tipo = 'group' then c.nombre else o.nombre_visible end as nombre,
        case when c.tipo = 'group' then null else o.ruta_avatar end as ruta_avatar,
        c.ultimo_mensaje_en,
        c.archivada,
        mem.rol,
        (
            select count(*)
            from public.miembros_conversacion x
            where x.conversacion_id = c.id and x.salido_en is null
        ) as total_miembros,
        (
            select count(*)
            from public.mensajes m
            where m.conversacion_id = c.id
              and m.eliminado_en is null
              and m.autor_id is distinct from :actor_id
              and m.creado_en > coalesce(mem.ultimo_leido_en, mem.unido_en)
        ) as no_leidos,
        lm.tipo as ultimo_tipo,
        lm.contenido as ultimo_contenido,
        (lm.eliminado_en is not null) as ultimo_eliminado,
        lm.autor_alias as ultimo_autor_alias
    from public.conversaciones c
    join public.miembros_conversacion mem
      on mem.conversacion_id = c.id
     and mem.usuario_id = :actor_id
     and mem.salido_en is null
    left join public.preferencias_conversacion pref
      on pref.conversacion_id = c.id
     and pref.usuario_id = :actor_id
    left join public.perfiles o
      on c.tipo = 'direct'
     and o.id = case when c.usuario_directo_menor = :actor_id
                     then c.usuario_directo_mayor
                     else c.usuario_directo_menor end
    left join lateral (
        select m.tipo, m.contenido, m.eliminado_en, a.alias as autor_alias
        from public.mensajes m
        left join public.perfiles a on a.id = m.autor_id
        where m.conversacion_id = c.id
        order by m.creado_en desc, m.id desc
        limit 1
    ) lm on true
    where c.eliminado_en is null
      and (cast(:include_hidden as boolean) or coalesce(pref.oculta, false) = false)
    order by c.ultimo_mensaje_en desc nulls last, c.id
    """
)


def _initials(name: str) -> str:
    """Iniciales para el avatar: dos palabras → una letra de cada una."""
    words = name.split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _preview(row) -> str | None:
    """Vista previa del último mensaje (§3.6, Q85)."""
    if row.ultimo_tipo is None:
        return None
    if row.ultimo_eliminado:
        return _DELETED_PREVIEW
    if row.ultimo_tipo == "poll":
        return _POLL_PREVIEW
    if row.ultimo_tipo == "system":
        return None
    content = " ".join((row.ultimo_contenido or "").split())[:_PREVIEW_LENGTH]
    if row.tipo == "group" and row.ultimo_autor_alias:
        return f"{row.ultimo_autor_alias}: {content}"
    return content


class ConversationRepository:
    """Acceso a `conversaciones`, `miembros_conversacion` y `mensajes`."""

    async def list_conversations(
        self, actor_id: str, *, include_hidden: bool = False
    ) -> ConversationList:
        """Lista de conversaciones del actor, la más reciente primero (§7.1).

        `total_unread` es la suma de no leídos de todas las conversaciones, no
        el número de hilos con mensajes sin leer.
        """
        actor = UUID(actor_id)
        async with actor_transaction(actor) as session:
            rows = (
                await session.execute(
                    _LIST_CONVERSATIONS_SQL,
                    {"actor_id": actor, "include_hidden": include_hidden},
                )
            ).all()
        items = [
            ConversationSummary(
                id=row.id,
                type=row.tipo,
                name=row.nombre or "Usuario",
                avatar_url=row.ruta_avatar,
                initials=_initials(row.nombre or "Usuario"),
                last_message_at=row.ultimo_mensaje_en,
                last_message_preview=_preview(row),
                unread_count=int(row.no_leidos),
                is_archived=bool(row.archivada),
                my_role=row.rol,
                members_count=int(row.total_miembros),
                is_discoverable=False,  # constante: su columna llega en 0013
                description=None,  # constante: su columna llega en 0013
            )
            for row in rows
        ]
        return ConversationList(
            items=items, total_unread=sum(item.unread_count for item in items)
        )


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    """Instancia única del repositorio por proceso."""
    return ConversationRepository()