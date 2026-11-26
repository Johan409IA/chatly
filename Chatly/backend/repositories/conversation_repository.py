"""Repositorio de conversaciones del chat: listado, detalle y ciclo de grupos.

Las tablas viven en `public` con RLS activa. Todas las consultas se hacen dentro
de `actor_transaction`, que fija `app.current_user_id`. Los nombres de columnas
están en español (AGENTS.md); las clases, funciones y variables en inglés.

Reglas de la Iteración 3 (docs/api-contracts.md §7):
- Grupos de 3–10 integrantes al crearse; el máximo de 10 activos también lo
  garantiza el trigger `trg_miembros_proteger_capacidad` (Q8, Q89).
- Crear/expulsar/renombrar solo el administrador activo (Q35, Q46, Q81).
- Al salir, el admin pasa al integrante activo con mayor antigüedad; el último
  integrante archiva la conversación (Q21, Q45, Q47).
- Añadir a alguien resuelve sus solicitudes pendientes en la misma
  transacción: este grupo → aceptada; otro grupo → rechazada; grupo lleno →
  rechazada por capacidad (Q130, Q144, Q166).
- Cada operación de membresía genera un mensaje de `system` auditable.
"""

import json
import logging
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from Chatly.backend.core.errors import (
    ConflictError,
    DomainError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from Chatly.backend.database.session import actor_transaction
from Chatly.backend.schemas.chat import (
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    DirectConversationResponse,
    LeaveResponse,
    MemberItem,
    MembershipCreated,
    MyMembership,
    UserSummary,
)
from Chatly.backend.schemas.profile import InterestTagDTO

logger = logging.getLogger(__name__)

_PREVIEW_LENGTH = 80
_DELETED_PREVIEW = "Se eliminó un mensaje"
_POLL_PREVIEW = "Encuesta"

_MAX_GROUP_MEMBERS = 10
_MIN_GROUP_MEMBERS = 3

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
        c.es_descubrible,
        c.descripcion,
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
                is_discoverable=bool(row.es_descubrible),
                description=row.descripcion,
            )
            for row in rows
        ]
        return ConversationList(items=items, total_unread=sum(item.unread_count for item in items))

    # ------------------------------------------------------------------
    # Detalle (§7.4)
    # ------------------------------------------------------------------

    _DETAIL_SQL = text(
        """
        select c.id, c.tipo, c.nombre, c.administrador_id, c.archivada,
               c.es_descubrible, c.descripcion, c.creado_en
        from public.conversaciones c
        where c.id = :conversation_id and c.eliminado_en is null
        """
    )
    _MEMBERS_SQL = text(
        """
        select p.id, p.alias, p.nombre_visible, p.ruta_avatar,
               m.rol, m.unido_en, m.salido_en
        from public.miembros_conversacion m
        join public.perfiles p on p.id = m.usuario_id
        where m.conversacion_id = :conversation_id
        order by (m.salido_en is null) desc, m.unido_en, m.id
        """
    )
    _INTERESTS_SQL = text(
        """
        select i.id, i.nombre, cat.nombre as categoria
        from public.intereses_conversacion ic
        join public.intereses i on i.id = ic.interes_id
        join public.categorias_interes cat on cat.id = i.categoria_id
        where ic.conversacion_id = :conversation_id
        order by cat.orden, lower(i.nombre)
        """
    )
    _MY_MEMBERSHIP_SQL = text(
        """
        select rol, unido_en, salido_en
        from public.miembros_conversacion
        where conversacion_id = :conversation_id and usuario_id = :actor_id
        order by unido_en desc
        limit 1
        """
    )

    async def get_conversation(self, actor_id: str, conversation_id: str) -> ConversationDetail:
        """Detalle con integrantes, admin y membresía propia (§7.4).

        La RLS solo deja ver la conversación a quien fue miembro en algún
        periodo; un ajeno recibe `404 not_found`.
        """
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            detail = await self._load_detail(session, actor, conversation)
        if detail is None:
            raise NotFoundError("La conversación no existe.")
        return detail

    async def _load_detail(
        self, session, actor: UUID, conversation: UUID
    ) -> ConversationDetail | None:
        row = (await session.execute(self._DETAIL_SQL, {"conversation_id": conversation})).first()
        if row is None:
            return None
        member_rows = (
            await session.execute(self._MEMBERS_SQL, {"conversation_id": conversation})
        ).all()
        interest_rows = (
            await session.execute(self._INTERESTS_SQL, {"conversation_id": conversation})
        ).all()
        my_row = (
            await session.execute(
                self._MY_MEMBERSHIP_SQL,
                {"conversation_id": conversation, "actor_id": actor},
            )
        ).first()
        members = [
            MemberItem(
                user=UserSummary(
                    id=m.id,
                    alias=m.alias,
                    display_name=m.nombre_visible,
                    avatar_url=m.ruta_avatar,
                ),
                role=m.rol,
                joined_at=m.unido_en,
                left_at=m.salido_en,
                active=m.salido_en is None,
            )
            for m in member_rows
        ]
        return ConversationDetail(
            id=row.id,
            type=row.tipo,
            name=row.nombre,
            admin_id=row.administrador_id,
            is_archived=bool(row.archivada),
            is_discoverable=bool(row.es_descubrible),
            description=row.descripcion,
            interests=[
                InterestTagDTO(id=i.id, name=i.nombre, category=i.categoria) for i in interest_rows
            ],
            created_at=row.creado_en,
            members=members,
            my_membership=(
                MyMembership(
                    role=my_row.rol,
                    active=my_row.salido_en is None,
                    joined_at=my_row.unido_en,
                )
                if my_row
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Chat directo (§7.2): solo vista previa; la fila se crea al enviar
    # el primer mensaje (Q20, Q146).
    # ------------------------------------------------------------------

    _PROFILE_SQL = text(
        """
        select id, alias, nombre_visible, ruta_avatar,
               (correo_verificado_en is not null) as verificado
        from public.perfiles
        where id = :recipient_id and eliminado_en is null
        """
    )
    _DIRECT_EXISTING_SQL = text(
        """
        select c.id, c.ultimo_mensaje_en, c.archivada, mem.rol,
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
               ) as no_leidos
        from public.conversaciones c
        join public.miembros_conversacion mem
          on mem.conversacion_id = c.id
         and mem.usuario_id = :actor_id
         and mem.salido_en is null
        where c.tipo = 'direct'
          and c.eliminado_en is null
          and c.usuario_directo_menor = least(:actor_id, :recipient_id)
          and c.usuario_directo_mayor = greatest(:actor_id, :recipient_id)
        """
    )

    async def get_or_preview_direct(
        self, actor_id: str, recipient_id: str
    ) -> DirectConversationResponse:
        """Conversación privada existente o vista previa temporal (§7.2).

        No inserta ninguna fila: la conversación nace al enviar el primer
        mensaje (Q146). `recipient` viene del servidor, nunca del cliente.
        """
        actor = UUID(actor_id)
        recipient = UUID(recipient_id)
        if actor == recipient:
            raise ValidationError("No puedes iniciar un chat contigo mismo.")
        async with actor_transaction(actor) as session:
            profile = (
                await session.execute(self._PROFILE_SQL, {"recipient_id": recipient})
            ).first()
            if profile is None:
                raise NotFoundError("Ese usuario no existe.")
            if not profile.verificado:
                raise ForbiddenError("Ese usuario aún no confirmó su correo.")
            recipient_dto = UserSummary(
                id=profile.id,
                alias=profile.alias,
                display_name=profile.nombre_visible,
                avatar_url=profile.ruta_avatar,
            )
            row = (
                await session.execute(
                    self._DIRECT_EXISTING_SQL,
                    {"actor_id": actor, "recipient_id": recipient},
                )
            ).first()
        if row is None:
            return DirectConversationResponse(
                conversation_id=None,
                is_temporary=True,
                conversation=None,
                recipient=recipient_dto,
            )
        summary = ConversationSummary(
            id=row.id,
            type="direct",
            name=recipient_dto.display_name,
            avatar_url=recipient_dto.avatar_url,
            initials=_initials(recipient_dto.display_name),
            last_message_at=row.ultimo_mensaje_en,
            last_message_preview=None,
            unread_count=int(row.no_leidos),
            is_archived=bool(row.archivada),
            my_role=row.rol,
            members_count=int(row.total_miembros),
            is_discoverable=False,
            description=None,
        )
        return DirectConversationResponse(
            conversation_id=row.id,
            is_temporary=False,
            conversation=summary,
            recipient=recipient_dto,
        )

    # ------------------------------------------------------------------
    # Grupos y membresías (§7.3, §7.5–7.9)
    # ------------------------------------------------------------------

    _GROUP_STATE_SQL = text(
        """
        select c.id, c.tipo, c.nombre, c.archivada,
               app.is_active_admin(c.id) as es_admin
        from public.conversaciones c
        where c.id = :conversation_id and c.eliminado_en is null
        """
    )
    _ACTIVE_MEMBER_EXISTS_SQL = text(
        """
        select true
        from public.miembros_conversacion
        where conversacion_id = :conversation_id
          and usuario_id = :user_id
          and salido_en is null
        """
    )
    _ANY_MEMBERSHIP_EXISTS_SQL = text(
        """
        select true
        from public.miembros_conversacion
        where conversacion_id = :conversation_id
          and usuario_id = :user_id
        limit 1
        """
    )
    _INSERT_MEMBERS_SQL = text(
        """
        insert into public.miembros_conversacion
            (conversacion_id, usuario_id, rol, agregado_por)
        select :conversation_id, x.uid, cast(:rol as text), cast(:agregado_por as uuid)
        from unnest(cast(:user_ids as uuid[])) as x(uid)
        returning id, usuario_id, unido_en
        """
    )
    _INSERT_SYSTEM_MESSAGE_SQL = text(
        """
        insert into public.mensajes
            (conversacion_id, autor_id, tipo, evento_sistema, datos_evento)
        values (:conversation_id, null, 'system', :event, cast(:data as jsonb))
        returning id
        """
    )

    async def _require_group_admin(self, session, conversation: UUID, actor: UUID):
        """Grupo visible para el actor y administrador activo; o error."""
        row = (
            await session.execute(self._GROUP_STATE_SQL, {"conversation_id": conversation})
        ).first()
        if row is None:
            raise NotFoundError("La conversación no existe.")
        if row.tipo != "group":
            raise ValidationError("Esta operación solo aplica a grupos.")
        if not row.es_admin:
            raise ForbiddenError("Solo el administrador puede hacer esto.")
        if row.archivada:
            raise ForbiddenError("El grupo está archivado.")
        return row

    async def create_group(
        self, actor_id: str, name: str, member_ids: list[str]
    ) -> ConversationDetail:
        """Crea el grupo con 3–10 integrantes; el creador es admin (§7.3).

        Todo en una transacción: conversación + membresías + mensaje de
        sistema `conversation_created`. El trigger de capacidad refuerza el
        máximo de 10 también bajo concurrencia (Q8, Q89).
        """
        actor = UUID(actor_id)
        clean_name = " ".join(name.split())
        others = list(dict.fromkeys(UUID(uid) for uid in member_ids if UUID(uid) != actor))
        total = len(others) + 1
        if total < _MIN_GROUP_MEMBERS:
            raise ValidationError(
                f"Un grupo necesita al menos {_MIN_GROUP_MEMBERS} integrantes contándote."
            )
        if total > _MAX_GROUP_MEMBERS:
            raise ConflictError(
                ErrorCode.CONVERSATION_FULL,
                f"Un grupo no puede superar {_MAX_GROUP_MEMBERS} integrantes.",
            )
        async with actor_transaction(actor) as session:
            found = (
                await session.execute(
                    text(
                        "select count(*) from public.perfiles "
                        "where id = any(cast(:user_ids as uuid[]))"
                    ),
                    {"user_ids": others},
                )
            ).scalar_one()
            if found != len(others):
                raise NotFoundError("Alguno de los integrantes no existe.")
            conversation_id = (
                await session.execute(
                    text(
                        "insert into public.conversaciones "
                        "(tipo, nombre, creado_por, administrador_id) "
                        "values ('group', :nombre, :actor_id, :actor_id) "
                        "returning id"
                    ),
                    {"nombre": clean_name, "actor_id": actor},
                )
            ).scalar_one()
            try:
                await session.execute(
                    self._INSERT_MEMBERS_SQL,
                    {
                        "conversation_id": conversation_id,
                        "user_ids": [actor],
                        "rol": "admin",
                        "agregado_por": None,
                    },
                )
                await session.execute(
                    self._INSERT_MEMBERS_SQL,
                    {
                        "conversation_id": conversation_id,
                        "user_ids": others,
                        "rol": "member",
                        "agregado_por": actor,
                    },
                )
            except IntegrityError as exc:
                raise self._translate_integrity(exc) from None
            await self._insert_system_message(
                session,
                conversation_id,
                "conversation_created",
                {"creado_por": str(actor), "nombre": clean_name},
            )
            detail = await self._load_detail(session, actor, conversation_id)
        assert detail is not None
        return detail

    async def rename_group(
        self, actor_id: str, conversation_id: str, name: str
    ) -> ConversationDetail:
        """Cambia el nombre; solo administrador activo (§7.5, Q46, Q87)."""
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        clean_name = " ".join(name.split())
        async with actor_transaction(actor) as session:
            state = await self._require_group_admin(session, conversation, actor)
            await session.execute(
                text("update public.conversaciones set nombre = :nombre where id = :id"),
                {"nombre": clean_name, "id": conversation},
            )
            await self._insert_system_message(
                session,
                conversation,
                "name_changed",
                {"nombre_anterior": state.nombre, "nombre_nuevo": clean_name},
            )
            detail = await self._load_detail(session, actor, conversation)
        assert detail is not None
        return detail

    async def add_member(
        self, actor_id: str, conversation_id: str, user_id: str
    ) -> MembershipCreated:
        """Incorpora un integrante y resuelve sus solicitudes (§7.6).

        En la misma transacción: la pendiente de este grupo se acepta
        (`direct_add_same_group`), las de otros grupos se rechazan
        (`joined_other_group`) y, si el grupo se llena, las pendientes de
        este grupo se rechazan por `group_full` (Q130, Q144, Q166).
        """
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        user = UUID(user_id)
        async with actor_transaction(actor) as session:
            await self._require_group_admin(session, conversation, actor)
            profile = (await session.execute(self._PROFILE_SQL, {"recipient_id": user})).first()
            if profile is None:
                raise NotFoundError("Ese usuario no existe.")
            if not profile.verificado:
                raise ForbiddenError(
                    "Ese usuario debe confirmar su correo antes de entrar al grupo."
                )
            already = (
                await session.execute(
                    self._ACTIVE_MEMBER_EXISTS_SQL,
                    {"conversation_id": conversation, "user_id": user},
                )
            ).first()
            if already:
                raise ConflictError(ErrorCode.ALREADY_MEMBER, "Ya es integrante del grupo.")
            has_capacity = (
                await session.execute(
                    text("select app.group_has_capacity(:conversation_id)"),
                    {"conversation_id": conversation},
                )
            ).scalar_one()
            if not has_capacity:
                raise ConflictError(
                    ErrorCode.CONVERSATION_FULL,
                    f"El grupo ya tiene {_MAX_GROUP_MEMBERS} integrantes.",
                )
            accepted = (
                (
                    await session.execute(
                        text(
                            "update public.solicitudes_union "
                            "set estado = 'accepted', "
                            "motivo_resolucion = 'direct_add_same_group', "
                            "resuelta_en = now(), resuelta_por = :actor_id, "
                            "actualizado_en = now() "
                            "where solicitante_id = :user_id "
                            "and conversacion_id = :conversation_id "
                            "and estado = 'pending' returning id"
                        ),
                        {
                            "actor_id": actor,
                            "user_id": user,
                            "conversation_id": conversation,
                        },
                    )
                )
                .scalars()
                .all()
            )
            try:
                inserted = (
                    await session.execute(
                        self._INSERT_MEMBERS_SQL,
                        {
                            "conversation_id": conversation,
                            "user_ids": [user],
                            "rol": "member",
                            "agregado_por": actor,
                        },
                    )
                ).first()
            except IntegrityError as exc:
                raise self._translate_integrity(exc) from None
            rejected_other = (
                (
                    await session.execute(
                        text(
                            "update public.solicitudes_union "
                            "set estado = 'rejected', motivo_resolucion = 'joined_other_group', "
                            "resuelta_en = now(), resuelta_por = :actor_id, actualizado_en = now() "
                            "where solicitante_id = :user_id and estado = 'pending' "
                            "and conversacion_id <> :conversation_id returning id"
                        ),
                        {
                            "actor_id": actor,
                            "user_id": user,
                            "conversation_id": conversation,
                        },
                    )
                )
                .scalars()
                .all()
            )
            full = (
                await session.execute(
                    text(
                        "select count(*) from public.miembros_conversacion "
                        "where conversacion_id = :conversation_id and salido_en is null"
                    ),
                    {"conversation_id": conversation},
                )
            ).scalar_one()
            rejected_full: list[UUID] = []
            if int(full) >= _MAX_GROUP_MEMBERS:
                rejected_full = (
                    (
                        await session.execute(
                            text(
                                "update public.solicitudes_union "
                                "set estado = 'rejected', "
                                "motivo_resolucion = 'group_full', "
                                "resuelta_en = now(), resuelta_por = :actor_id, "
                                "actualizado_en = now() "
                                "where conversacion_id = :conversation_id "
                                "and estado = 'pending' returning id"
                            ),
                            {"actor_id": actor, "conversation_id": conversation},
                        )
                    )
                    .scalars()
                    .all()
                )
            await self._insert_system_message(
                session, conversation, "member_added", {"usuario_id": str(user)}
            )
        return MembershipCreated(
            conversation_id=conversation,
            user_id=user,
            role="member",
            joined_at=inserted.unido_en,
            resolved_requests=[str(i) for i in (*accepted, *rejected_other, *rejected_full)],
        )

    async def remove_member(self, actor_id: str, conversation_id: str, user_id: str) -> None:
        """Expulsa a un integrante activo; solo administrador (§7.7, Q35)."""
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        user = UUID(user_id)
        async with actor_transaction(actor) as session:
            await self._require_group_admin(session, conversation, actor)
            if user == actor:
                raise ValidationError(
                    "No puedes expulsarte a ti mismo; usa «Salir de la conversación»."
                )
            membership = (
                await session.execute(
                    text(
                        "select id from public.miembros_conversacion "
                        "where conversacion_id = :conversation_id and usuario_id = :user_id "
                        "and salido_en is null"
                    ),
                    {"conversation_id": conversation, "user_id": user},
                )
            ).first()
            if membership is None:
                raise NotFoundError("Ese usuario no es integrante activo del grupo.")
            await session.execute(
                text(
                    "update public.miembros_conversacion "
                    "set salido_en = now(), estado = 'removed', retirado_por = :actor_id "
                    "where id = :membership_id"
                ),
                {"actor_id": actor, "membership_id": membership.id},
            )
            await self._insert_system_message(
                session, conversation, "member_removed", {"usuario_id": str(user)}
            )

    async def leave(self, actor_id: str, conversation_id: str, mode: str) -> LeaveResponse:
        """Salida con sucesión de admin y archivo si es el último (§7.8).

        `mode = 'hide'` además oculta la conversación para quien sale (Q21,
        Q30, Q45, Q47).
        """
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            membership = (
                await session.execute(
                    text(
                        "select id, rol from public.miembros_conversacion "
                        "where conversacion_id = :conversation_id and usuario_id = :actor_id "
                        "and salido_en is null"
                    ),
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
            if membership is None:
                raise NotFoundError("No perteneces a esta conversación.")
            await session.execute(
                text(
                    "update public.miembros_conversacion "
                    "set salido_en = now(), estado = 'left' where id = :membership_id"
                ),
                {"membership_id": membership.id},
            )
            archived = False
            new_admin_id: UUID | None = None
            if membership.rol == "admin":
                successor = (
                    await session.execute(
                        text(
                            "select usuario_id from public.miembros_conversacion "
                            "where conversacion_id = :conversation_id and salido_en is null "
                            "order by unido_en, id limit 1"
                        ),
                        {"conversation_id": conversation},
                    )
                ).first()
                if successor is not None:
                    new_admin_id = successor.usuario_id
                    await session.execute(
                        text(
                            "update public.miembros_conversacion set rol = 'admin' "
                            "where conversacion_id = :conversation_id and usuario_id = :user_id "
                            "and salido_en is null"
                        ),
                        {"conversation_id": conversation, "user_id": new_admin_id},
                    )
                else:
                    archived = True
                    await session.execute(
                        text(
                            "update public.conversaciones set archivada = true, "
                            "archivada_en = now() where id = :conversation_id"
                        ),
                        {"conversation_id": conversation},
                    )
            await self._insert_system_message(
                session,
                conversation,
                "member_left",
                {
                    "usuario_id": str(actor),
                    "nuevo_admin_id": str(new_admin_id) if new_admin_id else None,
                },
            )
            if mode == "hide":
                await self._upsert_preference(session, conversation, actor, True)
        return LeaveResponse(archived=archived, new_admin_id=new_admin_id)

    async def set_hidden(self, actor_id: str, conversation_id: str, hidden: bool) -> None:
        """Oculta o muestra la conversación para el actor (§7.9, Q59, Q68)."""
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            belongs = (
                await session.execute(
                    self._ANY_MEMBERSHIP_EXISTS_SQL,
                    {"conversation_id": conversation, "user_id": actor},
                )
            ).first()
            if belongs is None:
                raise NotFoundError("No perteneces a esta conversación.")
            await self._upsert_preference(session, conversation, actor, hidden)

    # ------------------------------------------------------------------
    # Comunes
    # ------------------------------------------------------------------

    async def _insert_system_message(
        self, session, conversation: UUID, event: str, data: dict
    ) -> None:
        """Mensaje de `system` con el evento y sus datos (§3.4)."""
        await session.execute(
            self._INSERT_SYSTEM_MESSAGE_SQL,
            {
                "conversation_id": conversation,
                "event": event,
                "data": json.dumps(data),
            },
        )

    async def _upsert_preference(
        self, session, conversation: UUID, actor: UUID, hidden: bool
    ) -> None:
        await session.execute(
            text(
                "insert into public.preferencias_conversacion "
                "(conversacion_id, usuario_id, oculta, ocultada_en) "
                "values (:conversation_id, :user_id, :hidden, "
                "case when :hidden then now() end) "
                "on conflict (conversacion_id, usuario_id) do update "
                "set oculta = excluded.oculta, ocultada_en = excluded.ocultada_en"
            ),
            {"conversation_id": conversation, "user_id": actor, "hidden": hidden},
        )

    @staticmethod
    def _translate_integrity(exc: IntegrityError) -> DomainError:
        """Traduce violaciones de unicidad esperadas a errores del contrato."""
        diag = getattr(exc.orig, "diag", None)
        constraint = str(getattr(diag, "constraint_name", "") or "")
        if not constraint:
            constraint = str(exc)
        if "uq_miembros_activos" in constraint:
            return ConflictError(ErrorCode.ALREADY_MEMBER, "Ya es integrante del grupo.")
        if "ck_miembros_capacidad" in constraint:
            return ConflictError(
                ErrorCode.CONVERSATION_FULL,
                f"El grupo ya tiene {_MAX_GROUP_MEMBERS} integrantes.",
            )
        raise exc


@lru_cache
def get_conversation_repository() -> ConversationRepository:
    """Instancia única del repositorio por proceso."""
    return ConversationRepository()
