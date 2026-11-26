"""Endpoints de conversaciones, grupos y mensajes (`docs/api-contracts.md` §7–§8).

Las reglas de negocio viven en `ConversationRepository` y `MessageRepository`
(patrón de `profile_repository.py`): todo se ejecuta dentro de
`actor_transaction` con RLS. Todos los endpoints exigen `VerifiedActor`: un
usuario sin confirmar no entra al chat (criterio de la Iteración 2).

Lecturas (§7.10) llegan en la Iteración 5.
"""

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Query, Response

from Chatly.backend.api.deps import (
    ConversationRepositoryDep,
    MessageRepositoryDep,
    VerifiedActor,
)
from Chatly.backend.schemas.chat import (
    AddMemberBody,
    ConversationDetail,
    ConversationList,
    CreateGroupBody,
    DirectConversationBody,
    DirectConversationResponse,
    DirectMessageBody,
    DirectMessageResponse,
    LeaveBody,
    LeaveResponse,
    MembershipCreated,
    MessageList,
    PreferencesBody,
    RenameGroupBody,
    SendMessageBody,
    SendMessageResponse,
)

router = APIRouter(tags=["chat"])


@router.get("/api/conversations", response_model=ConversationList)
async def list_conversations(
    actor: VerifiedActor,
    repository: ConversationRepositoryDep,
    include_hidden: bool = False,
) -> ConversationList:
    """Conversaciones del actor por último mensaje descendente (§7.1)."""
    return await repository.list_conversations(str(actor.id), include_hidden=include_hidden)


@router.post("/api/conversations/direct", response_model=DirectConversationResponse)
async def open_direct(
    actor: VerifiedActor,
    body: DirectConversationBody,
    repository: ConversationRepositoryDep,
) -> DirectConversationResponse:
    """Chat existente o temporal; no persiste nada (§7.2, Q20, Q146)."""
    return await repository.get_or_preview_direct(str(actor.id), str(body.recipient_id))


@router.post("/api/conversations/groups", response_model=ConversationDetail, status_code=201)
async def create_group(
    actor: VerifiedActor,
    body: CreateGroupBody,
    repository: ConversationRepositoryDep,
) -> ConversationDetail:
    """Crea el grupo con 3–10 integrantes; el creador es admin (§7.3)."""
    return await repository.create_group(
        str(actor.id), body.name, [str(uid) for uid in body.member_ids]
    )


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    actor: VerifiedActor,
    conversation_id: UUID,
    repository: ConversationRepositoryDep,
) -> ConversationDetail:
    """Detalle con integrantes, admin y membresía propia (§7.4)."""
    return await repository.get_conversation(str(actor.id), str(conversation_id))


@router.patch("/api/conversations/{conversation_id}", response_model=ConversationDetail)
async def rename_group(
    actor: VerifiedActor,
    conversation_id: UUID,
    body: RenameGroupBody,
    repository: ConversationRepositoryDep,
) -> ConversationDetail:
    """Cambia el nombre del grupo; solo administrador activo (§7.5)."""
    return await repository.rename_group(str(actor.id), str(conversation_id), body.name)


@router.post(
    "/api/conversations/{conversation_id}/members",
    response_model=MembershipCreated,
    status_code=201,
)
async def add_member(
    actor: VerifiedActor,
    conversation_id: UUID,
    body: AddMemberBody,
    repository: ConversationRepositoryDep,
) -> MembershipCreated:
    """Incorpora un integrante y resuelve sus solicitudes (§7.6)."""
    return await repository.add_member(str(actor.id), str(conversation_id), str(body.user_id))


@router.delete("/api/conversations/{conversation_id}/members/{user_id}", status_code=204)
async def remove_member(
    actor: VerifiedActor,
    conversation_id: UUID,
    user_id: UUID,
    repository: ConversationRepositoryDep,
) -> Response:
    """Expulsa a un integrante activo; solo administrador (§7.7)."""
    await repository.remove_member(str(actor.id), str(conversation_id), str(user_id))
    return Response(status_code=204)


@router.post("/api/conversations/{conversation_id}/leave", response_model=LeaveResponse)
async def leave_conversation(
    actor: VerifiedActor,
    conversation_id: UUID,
    body: LeaveBody,
    repository: ConversationRepositoryDep,
) -> LeaveResponse:
    """Salida con sucesión de admin y archivo si es el último (§7.8)."""
    return await repository.leave(str(actor.id), str(conversation_id), body.mode)


@router.put("/api/conversations/{conversation_id}/preferences", status_code=200)
async def set_preferences(
    actor: VerifiedActor,
    conversation_id: UUID,
    body: PreferencesBody,
    repository: ConversationRepositoryDep,
) -> dict[str, bool]:
    """Oculta o muestra la conversación para el actor (§7.9)."""
    await repository.set_hidden(str(actor.id), str(conversation_id), body.hidden)
    return {"hidden": body.hidden}


# ----------------------------------------------------------------------
# Mensajes (§7.2.1 y §8)
# ----------------------------------------------------------------------


@router.get("/api/conversations/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    actor: VerifiedActor,
    conversation_id: UUID,
    repository: MessageRepositoryDep,
    before_created_at: datetime | None = None,
    before_id: UUID | None = None,
    limit: int | None = Query(default=None, ge=1, le=50),
) -> MessageList:
    """Historial ascendente con paginación por cursor (§8.1, Q94)."""
    return await repository.list_messages(
        str(actor.id),
        str(conversation_id),
        before_created_at=before_created_at,
        before_id=before_id,
        limit=limit,
    )


@router.post("/api/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    actor: VerifiedActor,
    conversation_id: UUID,
    body: SendMessageBody,
    repository: MessageRepositoryDep,
    response: Response,
) -> SendMessageResponse:
    """Envía un mensaje de texto con idempotencia (§8.2, Q40).

    `201` cuando se crea; `200` si `client_message_id` ya existía.
    """
    client_message_id = body.client_message_id or uuid4()
    result = await repository.send_message(
        str(actor.id),
        str(conversation_id),
        body.content,
        client_message_id,
        body.reply_to_message_id,
    )
    response.status_code = 200 if result.idempotent_replay else 201
    return SendMessageResponse(message=result.message, idempotent_replay=result.idempotent_replay)


@router.post("/api/messages/direct", response_model=DirectMessageResponse)
async def send_direct_message(
    actor: VerifiedActor,
    body: DirectMessageBody,
    repository: MessageRepositoryDep,
    response: Response,
) -> DirectMessageResponse:
    """Primer mensaje de un chat privado; crea la conversación si no existe (§7.2.1, Q146)."""
    client_message_id = body.client_message_id or uuid4()
    result = await repository.send_direct_message(
        str(actor.id), str(body.recipient_id), body.content, client_message_id
    )
    response.status_code = 200 if not result.conversation_created else 201
    return DirectMessageResponse(
        message=result.message,
        conversation_id=result.conversation_id,
        idempotent_replay=result.idempotent_replay,
    )
