"""Endpoints del chat directo 1:1 (`docs/api-contracts.md` §7)."""

from fastapi import APIRouter

from Chatly.backend.api.deps import ConversationRepositoryDep, VerifiedActor
from Chatly.backend.schemas.chat import ConversationList

router = APIRouter(tags=["chat"])


@router.get("/api/conversations", response_model=ConversationList)
async def list_conversations(
    actor: VerifiedActor,
    repository: ConversationRepositoryDep,
    include_hidden: bool = False,
) -> ConversationList:
    """Conversaciones del actor por último mensaje descendente (§7.1)."""
    return await repository.list_conversations(str(actor.id), include_hidden=include_hidden)
