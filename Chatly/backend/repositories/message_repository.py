"""Repositorio de mensajes: historial paginado y envío de texto.

Sigue el patrón repo-enforces de `conversation_repository.py`: toda regla de
negocio vive aquí, dentro de `actor_transaction` con RLS activa. La RLS ya
filtra la lectura por periodos de membresía (`mensajes_select_por_periodo`)
y la escritura por membresía activa (`mensajes_insert_backend`); el
repositorio traduce las violaciones a errores del contrato.

Contratos (`docs/api-contracts.md`):
- §8.1 `GET /api/conversations/{id}/messages`: 50 últimos sin cursor y 30
  anteriores con cursor `(before_created_at, before_id)`, orden estable por
  `(creado_en, id)` (Q94).
- §8.2 `POST /api/conversations/{id}/messages`: idempotencia por
  `(autor_id, id_mensaje_cliente)` (Q40), contenido de 1–4.000 caracteres
  (Q51) y respuesta dentro de la misma conversación (Q75).
- §7.2.1 `POST /api/messages/direct`: la conversación privada nace al enviar
  el primer mensaje, todo en una transacción (Q20, Q146).
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError

from Chatly.backend.core.errors import (
    DomainError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from Chatly.backend.database.session import actor_transaction
from Chatly.backend.schemas.chat import (
    Message,
    MessageAuthor,
    MessageCursor,
    MessageList,
    ReadResponse,
    ReadStatus,
    ReplyPreview,
)
from Chatly.backend.services.typing_registry import get_typing_registry

logger = logging.getLogger(__name__)

_FIRST_PAGE_SIZE = 50
_NEXT_PAGE_SIZE = 30
_MAX_CONTENT_LENGTH = 4000
_PREVIEW_LENGTH = 80
_DELETED_PREVIEW = "Se eliminó un mensaje"
_POLL_PREVIEW = "Encuesta"

_AUTHOR_FIELDS = """
    a.id as autor_id, a.alias as autor_alias,
    a.nombre_visible as autor_nombre, a.ruta_avatar as autor_avatar
"""

_REPLY_JOIN = """
    left join public.mensajes r on r.id = m.mensaje_respuesta_id
    left join public.perfiles ra on ra.id = r.autor_id
"""

_REPLY_FIELDS = """
    r.id as respuesta_id, ra.alias as respuesta_alias,
    r.contenido as respuesta_contenido, r.tipo as respuesta_tipo,
    (r.eliminado_en is not null) as respuesta_eliminada,
    r.evento_sistema as respuesta_evento
"""

# Historial de una conversación: el índice `ix_mensajes_conversacion_cursor`
# cubre el filtro y el orden descendente; se invierte en Python. El lateral
# calcula el `ReadStatus` (§3.4) con las reglas Q22/Q48/Q101: no cuenta el
# emisor, solo integrantes activos presentes al enviarse el mensaje, y quien
# sale sin leer deja de bloquear el ✓✓.
_LIST_MESSAGES_SQL = text(
    f"""
    select m.id, m.conversacion_id, m.tipo, m.contenido, m.evento_sistema,
           m.datos_evento, m.mensaje_respuesta_id, m.editado_en,
           (m.eliminado_en is not null) as eliminado, m.creado_en,
           {_AUTHOR_FIELDS},
           {_REPLY_FIELDS},
           lect.esperados, lect.leidos
    from public.mensajes m
    left join public.perfiles a on a.id = m.autor_id
    {_REPLY_JOIN}
    left join lateral (
        select count(*) as esperados,
               count(*) filter (
                   where coalesce(mem.ultimo_leido_en, mem.unido_en) >= m.creado_en
               ) as leidos
        from public.miembros_conversacion mem
        where mem.conversacion_id = m.conversacion_id
          and mem.usuario_id is distinct from m.autor_id
          and mem.unido_en <= m.creado_en
          and mem.salido_en is null
    ) lect on true
    where m.conversacion_id = :conversation_id
      and ((cast(:before_created_at as timestamptz) is null
            and cast(:before_id as uuid) is null)
           or (m.creado_en, m.id) < (cast(:before_created_at as timestamptz),
                                     cast(:before_id as uuid)))
    order by m.creado_en desc, m.id desc
    limit :limit
    """
)

_CONVERSATION_EXISTS_SQL = text(
    """
    select true from public.conversaciones
    where id = :conversation_id and eliminado_en is null
    """
)

_MEMBERSHIP_SQL = text(
    """
    select salido_en from public.miembros_conversacion
    where conversacion_id = :conversation_id and usuario_id = :actor_id
    order by unido_en desc limit 1
    """
)

_MESSAGE_READ_SQL = text(
    """
    select id, creado_en from public.mensajes
    where id = :message_id and conversacion_id = :conversation_id
      and eliminado_en is null
    """
)

# §7.10: nunca retrocede la marca (`greatest`) y solo apunta el mensaje como
# último leído cuando de verdad avanza. `RETURNING` pasa la política SELECT
# (`miembros_select_backend`): el actor es miembro de la conversación.
_MARK_READ_SQL = text(
    """
    update public.miembros_conversacion
       set ultimo_leido_en = greatest(coalesce(ultimo_leido_en, unido_en), :read_at),
           ultimo_mensaje_leido_id = case
               when :read_at >= coalesce(ultimo_leido_en, unido_en) then :message_id
               else ultimo_mensaje_leido_id end,
           actualizado_en = now()
     where conversacion_id = :conversation_id
       and usuario_id = :actor_id
       and salido_en is null
    returning ultimo_mensaje_leido_id, ultimo_leido_en
    """
)

_ALIAS_SQL = text(
    """
    select coalesce(nombre_visible, alias) as nombre
    from public.perfiles
    where eliminado_en is null and id in :user_ids
    order by nombre
    """
).bindparams(bindparam("user_ids", expanding=True))

# Idempotencia (Q40): la clave única es (autor_id, id_mensaje_cliente).
_FIND_BY_CLIENT_ID_SQL = text(
    f"""
    select m.id, m.conversacion_id, m.tipo, m.contenido, m.evento_sistema,
           m.datos_evento, m.mensaje_respuesta_id, m.editado_en,
           (m.eliminado_en is not null) as eliminado, m.creado_en,
           {_AUTHOR_FIELDS},
           {_REPLY_FIELDS}
    from public.mensajes m
    left join public.perfiles a on a.id = m.autor_id
    {_REPLY_JOIN}
    where m.autor_id = :actor_id and m.id_mensaje_cliente = :client_message_id
    """
)

_REPLY_SQL = text(
    """
    select m.id, m.contenido, m.tipo, m.evento_sistema,
           (m.eliminado_en is not null) as eliminada,
           ra.alias as autor_alias
    from public.mensajes m
    left join public.perfiles ra on ra.id = m.autor_id
    where m.id = :reply_id and m.conversacion_id = :conversation_id
    """
)

_INSERT_MESSAGE_SQL = text(
    """
    insert into public.mensajes
        (conversacion_id, autor_id, tipo, contenido, mensaje_respuesta_id,
         id_mensaje_cliente)
    values (:conversation_id, :actor_id, 'text', :content,
            :reply_to, :client_message_id)
    returning id, creado_en
    """
)

_PROFILE_SQL = text(
    """
    select id, alias, nombre_visible, ruta_avatar,
           (correo_verificado_en is not null) as verificado
    from public.perfiles
    where id = :user_id and eliminado_en is null
    """
)

_PAIR_CONVERSATION_SQL = text(
    """
    select c.id
    from public.conversaciones c
    where c.tipo = 'direct'
      and c.eliminado_en is null
      and c.usuario_directo_menor = least(:actor_id, :recipient_id)
      and c.usuario_directo_mayor = greatest(:actor_id, :recipient_id)
    """
)

# Sin `returning id`: con RLS activa, `RETURNING` exige que la fila nueva
# pase la política SELECT (`has_membership`), imposible antes de insertar las
# membresías. El `id` lo genera la aplicación (0014_rls_chat_directo).
_INSERT_DIRECT_CONVERSATION_SQL = text(
    """
    insert into public.conversaciones
        (id, tipo, creado_por, usuario_directo_menor, usuario_directo_mayor)
    values (:id, 'direct', :actor_id, :menor, :mayor)
    """
)

_INSERT_MEMBERSHIP_SQL = text(
    """
    insert into public.miembros_conversacion (conversacion_id, usuario_id, rol)
    values (:conversation_id, :user_id, 'member')
    """
)


@dataclass(frozen=True)
class SendResult:
    """Resultado de un envío: el mensaje y si fue creación o reintento."""

    message: Message
    idempotent_replay: bool
    conversation_id: UUID
    conversation_created: bool = False


def _reply_preview(row) -> ReplyPreview | None:
    """Referencia de respuesta visible en la burbuja (Q75, Q85)."""
    if getattr(row, "respuesta_id", None) is None:
        return None
    if row.respuesta_eliminada:
        preview = _DELETED_PREVIEW
    elif row.respuesta_tipo == "poll":
        preview = _POLL_PREVIEW
    elif row.respuesta_tipo == "system":
        preview = row.respuesta_evento or "Actualización de la conversación"
    else:
        preview = " ".join((row.respuesta_contenido or "").split())[:_PREVIEW_LENGTH]
    return ReplyPreview(id=row.respuesta_id, author_alias=row.respuesta_alias, preview=preview)


def _build_message(row) -> Message:
    """Convierte una fila del historial al DTO `Message` (§3.4)."""
    author = None
    if row.autor_id is not None:
        author = MessageAuthor(
            id=row.autor_id,
            alias=row.autor_alias or "",
            display_name=row.autor_nombre or "",
            avatar_url=row.autor_avatar,
        )
    deleted = bool(row.eliminado)
    # El `ReadStatus` solo viene en las filas del historial (lateral de
    # `_LIST_MESSAGES_SQL`) y solo aplica a mensajes de texto propios:
    # los de sistema y los ajenos no llevan marca de lectura.
    esperados = getattr(row, "esperados", None)
    read = None
    if author is not None and row.tipo == "text" and esperados is not None:
        read = ReadStatus(
            all_read=int(row.leidos) >= int(esperados),
            read_count=int(row.leidos),
            expected_count=int(esperados),
        )
    return Message(
        id=row.id,
        conversation_id=row.conversacion_id,
        type=row.tipo,
        author=author,
        content=None if deleted else row.contenido,
        edited_at=row.editado_en,
        deleted=deleted,
        reply_to=_reply_preview(row),
        read=read,
        system_event=row.evento_sistema,
        system_data=row.datos_evento,
        created_at=row.creado_en,
    )


class MessageRepository:
    """Acceso a `mensajes` para historial y envío de texto."""

    async def list_messages(
        self,
        actor_id: str,
        conversation_id: str,
        *,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
        limit: int | None = None,
    ) -> MessageList:
        """Historial ascendente con paginación por cursor (§8.1, Q94).

        Sin cursor devuelve los últimos 50; con cursor, los 30 anteriores.
        La RLS ya limita la lectura a los periodos de membresía del actor
        (Q104): aquí solo se pagina y se ordena de forma estable.
        """
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        if (before_created_at is None) != (before_id is None):
            raise ValidationError("El cursor necesita `before_created_at` y `before_id` juntos.")
        if before_created_at is not None and before_created_at.tzinfo is None:
            raise ValidationError("La marca de tiempo del cursor debe incluir la zona horaria.")
        if limit is not None and not 1 <= limit <= _FIRST_PAGE_SIZE:
            raise ValidationError(f"El límite debe estar entre 1 y {_FIRST_PAGE_SIZE}.")
        page_size = limit or (_FIRST_PAGE_SIZE if before_created_at is None else _NEXT_PAGE_SIZE)
        async with actor_transaction(actor) as session:
            exists = (
                await session.execute(_CONVERSATION_EXISTS_SQL, {"conversation_id": conversation})
            ).first()
            if exists is None:
                raise NotFoundError("La conversación no existe.")
            membership = (
                await session.execute(
                    _MEMBERSHIP_SQL,
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
            if membership is None:
                # La RLS tampoco dejaría ver nada: mismo resultado que un ajeno.
                raise NotFoundError("La conversación no existe.")
            rows = (
                await session.execute(
                    _LIST_MESSAGES_SQL,
                    {
                        "conversation_id": conversation,
                        "before_created_at": before_created_at,
                        "before_id": before_id,
                        "limit": page_size,
                    },
                )
            ).all()
        items = [_build_message(row) for row in reversed(rows)]
        next_cursor = None
        if len(rows) == page_size and rows:
            oldest = rows[-1]
            next_cursor = MessageCursor(created_at=oldest.creado_en, id=oldest.id)
        return MessageList(items=items, next_cursor=next_cursor)

    async def send_message(
        self,
        actor_id: str,
        conversation_id: str,
        content: str,
        client_message_id: UUID,
        reply_to_message_id: UUID | None = None,
    ) -> SendResult:
        """Envía un mensaje de texto a una conversación (§8.2)."""
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        cleaned = content.strip()
        if not cleaned:
            raise ValidationError("Escribe un mensaje antes de enviarlo.")
        if len(cleaned) > _MAX_CONTENT_LENGTH:
            raise DomainError(
                ErrorCode.MESSAGE_TOO_LONG,
                "El mensaje no puede superar los 4.000 caracteres.",
                status_code=422,
            )
        async with actor_transaction(actor) as session:
            replay = (
                await session.execute(
                    _FIND_BY_CLIENT_ID_SQL,
                    {"actor_id": actor, "client_message_id": client_message_id},
                )
            ).first()
            if replay is not None:
                return SendResult(
                    message=_build_message(replay),
                    idempotent_replay=True,
                    conversation_id=replay.conversacion_id,
                )
            exists = (
                await session.execute(_CONVERSATION_EXISTS_SQL, {"conversation_id": conversation})
            ).first()
            if exists is None:
                raise NotFoundError("La conversación no existe.")
            membership = (
                await session.execute(
                    _MEMBERSHIP_SQL,
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
            if membership is None:
                raise ForbiddenError("No perteneces a esta conversación.")
            if membership.salido_en is not None:
                raise DomainError(
                    ErrorCode.READ_ONLY_PERIOD,
                    "Ya no perteneces a esta conversación: solo puedes leer tu historial.",
                    status_code=403,
                )
            reply = None
            if reply_to_message_id is not None:
                reply = (
                    await session.execute(
                        _REPLY_SQL,
                        {"reply_id": reply_to_message_id, "conversation_id": conversation},
                    )
                ).first()
                if reply is None:
                    raise ValidationError(
                        "El mensaje al que respondes no pertenece a esta conversación."
                    )
            try:
                inserted = (
                    await session.execute(
                        _INSERT_MESSAGE_SQL,
                        {
                            "conversation_id": conversation,
                            "actor_id": actor,
                            "content": cleaned,
                            "reply_to": reply_to_message_id,
                            "client_message_id": client_message_id,
                        },
                    )
                ).first()
            except IntegrityError as exc:
                replay = (
                    await session.execute(
                        _FIND_BY_CLIENT_ID_SQL,
                        {"actor_id": actor, "client_message_id": client_message_id},
                    )
                ).first()
                if replay is not None:
                    return SendResult(
                        message=_build_message(replay),
                        idempotent_replay=True,
                        conversation_id=replay.conversacion_id,
                    )
                raise self._translate_integrity(exc) from None
            message = await self._load_message(session, inserted.id)
        return SendResult(
            message=message,
            idempotent_replay=False,
            conversation_id=conversation,
        )

    async def send_direct_message(
        self,
        actor_id: str,
        recipient_id: str,
        content: str,
        client_message_id: UUID,
    ) -> SendResult:
        """Primer mensaje de un chat privado (§7.2.1, Q20, Q146).

        Si la pareja ya tiene conversación, la reutiliza y añade el mensaje
        (200); si no, crea conversación, las dos membresías y el mensaje en
        una misma transacción (201).
        """
        actor = UUID(actor_id)
        recipient = UUID(recipient_id)
        if actor == recipient:
            raise ValidationError("No puedes iniciar un chat contigo mismo.")
        cleaned = content.strip()
        if not cleaned:
            raise ValidationError("Escribe un mensaje antes de enviarlo.")
        if len(cleaned) > _MAX_CONTENT_LENGTH:
            raise DomainError(
                ErrorCode.MESSAGE_TOO_LONG,
                "El mensaje no puede superar los 4.000 caracteres.",
                status_code=422,
            )
        async with actor_transaction(actor) as session:
            replay = (
                await session.execute(
                    _FIND_BY_CLIENT_ID_SQL,
                    {"actor_id": actor, "client_message_id": client_message_id},
                )
            ).first()
            if replay is not None:
                return SendResult(
                    message=_build_message(replay),
                    idempotent_replay=True,
                    conversation_id=replay.conversacion_id,
                )
            recipient_profile = (
                await session.execute(_PROFILE_SQL, {"user_id": recipient})
            ).first()
            if recipient_profile is None:
                raise NotFoundError("Ese usuario no existe.")
            if not recipient_profile.verificado:
                raise ForbiddenError("Ese usuario aún no confirmó su correo.")
            pair = (
                await session.execute(
                    _PAIR_CONVERSATION_SQL,
                    {"actor_id": actor, "recipient_id": recipient},
                )
            ).first()
            created = pair is None
            if created:
                conversation_id = uuid4()
                await session.execute(
                    _INSERT_DIRECT_CONVERSATION_SQL,
                    {
                        "id": conversation_id,
                        "actor_id": actor,
                        "menor": min(actor, recipient),
                        "mayor": max(actor, recipient),
                    },
                )
                await session.execute(
                    _INSERT_MEMBERSHIP_SQL,
                    {"conversation_id": conversation_id, "user_id": actor},
                )
                await session.execute(
                    _INSERT_MEMBERSHIP_SQL,
                    {"conversation_id": conversation_id, "user_id": recipient},
                )
            else:
                conversation_id = pair.id
            try:
                inserted = (
                    await session.execute(
                        _INSERT_MESSAGE_SQL,
                        {
                            "conversation_id": conversation_id,
                            "actor_id": actor,
                            "content": cleaned,
                            "reply_to": None,
                            "client_message_id": client_message_id,
                        },
                    )
                ).first()
            except IntegrityError as exc:
                replay = (
                    await session.execute(
                        _FIND_BY_CLIENT_ID_SQL,
                        {"actor_id": actor, "client_message_id": client_message_id},
                    )
                ).first()
                if replay is not None:
                    return SendResult(
                        message=_build_message(replay),
                        idempotent_replay=True,
                        conversation_id=replay.conversacion_id,
                    )
                raise self._translate_integrity(exc) from None
            message = await self._load_message(session, inserted.id)
        return SendResult(
            message=message,
            idempotent_replay=False,
            conversation_id=conversation_id,
            conversation_created=created,
        )

    async def is_active_member(self, actor_id: str, conversation_id: str) -> bool:
        """¿Tiene el actor una membresía activa en la conversación?"""
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            membership = (
                await session.execute(
                    _MEMBERSHIP_SQL,
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
        return membership is not None and membership.salido_en is None

    async def mark_read(
        self, actor_id: str, conversation_id: str, message_id: UUID
    ) -> ReadResponse:
        """Marca la lectura del último mensaje visible (§7.10, Q60, Q101).

        Solo avanza: `greatest` impide retroceder `ultimo_leido_en` si el
        cliente envía un mensaje más antiguo que el ya leído. Con esto
        `unread_count` (§7.1) baja solo y el ✓✓ del emisor aparece al
        releer el historial.
        """
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            exists = (
                await session.execute(_CONVERSATION_EXISTS_SQL, {"conversation_id": conversation})
            ).first()
            if exists is None:
                raise NotFoundError("La conversación no existe.")
            membership = (
                await session.execute(
                    _MEMBERSHIP_SQL,
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
            if membership is None:
                raise NotFoundError("La conversación no existe.")
            if membership.salido_en is not None:
                raise ForbiddenError("Ya no perteneces a esta conversación.")
            message = (
                await session.execute(
                    _MESSAGE_READ_SQL,
                    {"message_id": message_id, "conversation_id": conversation},
                )
            ).first()
            if message is None:
                raise ValidationError("Ese mensaje no pertenece a esta conversación.")
            row = (
                await session.execute(
                    _MARK_READ_SQL,
                    {
                        "conversation_id": conversation,
                        "actor_id": actor,
                        "message_id": message.id,
                        "read_at": message.creado_en,
                    },
                )
            ).first()
        if row is None:
            raise NotFoundError("La conversación no existe.")
        return ReadResponse(
            last_read_message_id=row.ultimo_mensaje_leido_id,
            last_read_at=row.ultimo_leido_en,
        )

    async def record_typing(
        self, actor_id: str, conversation_id: str, *, is_typing: bool
    ) -> None:
        """Registra la señal efímera de escritura del actor.

        Puente REST hasta la Iteración 6 (Broadcast `typing` en
        `conversation:<uuid>`): no persiste nada y la señal caduca sola.
        """
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            membership = (
                await session.execute(
                    _MEMBERSHIP_SQL,
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
            if membership is None or membership.salido_en is not None:
                raise ForbiddenError("No perteneces a esta conversación.")
        get_typing_registry().record_typing(
            conversation, actor, is_typing=is_typing
        )

    async def list_typing(self, actor_id: str, conversation_id: str) -> list[str]:
        """Nombres visibles de quienes están escribiendo (excluye al actor)."""
        actor = UUID(actor_id)
        conversation = UUID(conversation_id)
        async with actor_transaction(actor) as session:
            membership = (
                await session.execute(
                    _MEMBERSHIP_SQL,
                    {"conversation_id": conversation, "actor_id": actor},
                )
            ).first()
            if membership is None or membership.salido_en is not None:
                raise ForbiddenError("No perteneces a esta conversación.")
            user_ids = get_typing_registry().typing_members(
                conversation, exclude_user_id=actor
            )
            if not user_ids:
                return []
            rows = (await session.execute(_ALIAS_SQL, {"user_ids": user_ids})).all()
        return [row.nombre for row in rows]

    async def _load_message(self, session, message_id: UUID) -> Message:
        """Recarga el mensaje insertado con su autor y su respuesta."""
        row = (
            await session.execute(
                text(
                    f"""
                    select m.id, m.conversacion_id, m.tipo, m.contenido,
                           m.evento_sistema, m.datos_evento, m.mensaje_respuesta_id,
                           m.editado_en, (m.eliminado_en is not null) as eliminado,
                           m.creado_en,
                           {_AUTHOR_FIELDS},
                           {_REPLY_FIELDS}
                    from public.mensajes m
                    left join public.perfiles a on a.id = m.autor_id
                    {_REPLY_JOIN}
                    where m.id = :message_id
                    """
                ),
                {"message_id": message_id},
            )
        ).first()
        if row is None:
            raise NotFoundError("El mensaje no está disponible.")
        return _build_message(row)

    @staticmethod
    def _translate_integrity(exc: IntegrityError) -> DomainError:
        """Traduce violaciones esperadas a errores del contrato."""
        diag = getattr(exc.orig, "diag", None)
        constraint = str(getattr(diag, "constraint_name", "") or "")
        if not constraint:
            constraint = str(exc)
        if "fk_mensajes_respuesta" in constraint:
            return ValidationError("El mensaje al que respondes no pertenece a esta conversación.")
        if "ck_mensajes_contenido" in constraint:
            return DomainError(
                ErrorCode.MESSAGE_TOO_LONG,
                "El mensaje no puede superar los 4.000 caracteres.",
                status_code=422,
            )
        logger.warning("Violación de integridad al guardar mensaje: %s", constraint)
        raise exc


@lru_cache
def get_message_repository() -> MessageRepository:
    """Instancia única del repositorio por proceso."""
    return MessageRepository()
