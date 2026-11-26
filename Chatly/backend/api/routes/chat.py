"""Endpoints de conversaciones y grupos (`docs/api-contracts.md` §7).

Las reglas de negocio viven en `ConversationRepository` (patrón de
`profile_repository.py`): todo se ejecuta dentro de `actor_transaction` con
RLS. Todos los endpoints exigen `VerifiedActor`: un usuario sin confirmar
no entra al chat (criterio de la Iteración 2).

Mensajes (§7.2.1 y §8) llegan en la Iteración 4 y lecturas (§7.10) en la 5.
"""

from uuid import UUID

from fastapi import APIRouter, Response

from Chatly.backend.api.deps import ConversationRepositoryDep, VerifiedActor
from Chatly.backend.schemas.chat import (
    AddMemberBody,
    ConversationDetail,
    ConversationList,
    CreateGroupBody,
    DirectConversationBody,
    DirectConversationResponse,
    LeaveBody,
    LeaveResponse,
    MembershipCreated,
    PreferencesBody,
    RenameGroupBody,
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
