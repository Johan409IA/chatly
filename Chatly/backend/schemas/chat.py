from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from Chatly.backend.schemas.profile import InterestTagDTO


# ---------- Usuario (§3.1) ----------
class UserSummary(BaseModel):
    """Datos básicos de un perfil: nunca incluye el correo (§3.1)."""

    id: UUID
    alias: str
    display_name: str
    avatar_url: str | None = None


# ---------- Mensajes (§3.4) ----------
class MessageAuthor(BaseModel):
    id: UUID
    alias: str
    display_name: str
    avatar_url: str | None = None


class ReplyPreview(BaseModel):
    id: UUID
    author_alias: str | None = None
    preview: str | None = None


class ReactionSummary(BaseModel):
    emoji: str
    count: int
    reacted_by_me: bool


class ReadStatus(BaseModel):
    all_read: bool
    read_count: int
    expected_count: int


class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    type: str = "text"  # "text", "system" o "poll"
    author: MessageAuthor | None = None  # null si type == "system"
    content: str | None = None  # null si deleted == true
    edited_at: datetime | None = None
    deleted: bool = False
    reply_to: ReplyPreview | None = None
    reactions: list[ReactionSummary] = Field(default_factory=list)  # aplazado: vacío
    read: ReadStatus | None = None
    system_event: str | None = None  # solo si type == "system"
    system_data: dict | None = None  # solo si type == "system"
    poll: dict | None = None  # solo si type == "poll"
    created_at: datetime


class MessageCursor(BaseModel):
    created_at: datetime
    id: UUID


class MessageList(BaseModel):
    items: list[Message]  # orden ascendente (antiguo -> reciente)
    next_cursor: MessageCursor | None = None


# ---------- Conversaciones (§3.6) ----------
class ConversationSummary(BaseModel):
    id: UUID
    type: str  # "direct" o "group"
    name: str
    avatar_url: str | None = None
    initials: str
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    unread_count: int = 0
    is_archived: bool = False
    my_role: str
    members_count: int
    is_discoverable: bool = False
    description: str | None = None


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total_unread: int = 0  # suma de no leídos, no el conteo de hilos


# ---------- Detalle y membresías (§7.4) ----------
class MemberItem(BaseModel):
    """Integrante del detalle: activo o con su periodo histórico (§7.4)."""

    user: UserSummary
    role: Literal["admin", "member"]
    joined_at: datetime
    left_at: datetime | None = None
    active: bool


class MyMembership(BaseModel):
    """La membresía del actor dentro del detalle (§7.4)."""

    role: Literal["admin", "member"]
    active: bool
    joined_at: datetime


class ConversationDetail(BaseModel):
    """Detalle de conversación/grupo (§7.4): integrantes y descubribilidad."""

    id: UUID
    type: str
    name: str | None = None
    admin_id: UUID | None = None
    is_archived: bool = False
    is_discoverable: bool = False
    description: str | None = None
    interests: list[InterestTagDTO] = Field(default_factory=list)
    created_at: datetime
    members: list[MemberItem] = Field(default_factory=list)
    my_membership: MyMembership | None = None


class MembershipCreated(BaseModel):
    """Respuesta de `POST /api/conversations/{id}/members` (§7.6)."""

    conversation_id: UUID
    user_id: UUID
    role: Literal["admin", "member"]
    joined_at: datetime
    resolved_requests: list[str] = Field(default_factory=list)


# ---------- Cuerpos de petición ----------
# El límite de 4.000 caracteres (Q51) lo aplica el repositorio para responder
# `message_too_long` (§8.2) en lugar de un `validation_error` genérico.
class SendMessageBody(BaseModel):
    content: str = Field(min_length=1)
    client_message_id: UUID | None = None
    reply_to_message_id: UUID | None = None


class SendMessageResponse(BaseModel):
    message: Message
    idempotent_replay: bool = False


class DirectMessageBody(BaseModel):
    recipient_id: UUID
    content: str = Field(min_length=1)
    client_message_id: UUID | None = None


class DirectMessageResponse(BaseModel):
    message: Message
    conversation_id: UUID
    idempotent_replay: bool = False  # el contrato no define este cuerpo: confirmar


class ReadBody(BaseModel):
    message_id: UUID


class ReadResponse(BaseModel):
    last_read_message_id: UUID
    last_read_at: datetime


class TypingBody(BaseModel):
    """Cuerpo de `POST /api/conversations/{id}/typing` (puente hasta Realtime)."""

    is_typing: bool = True


# ---------- Cuerpos de conversaciones y grupos (§7.2–7.9) ----------
class DirectConversationBody(BaseModel):
    """Cuerpo de `POST /api/conversations/direct` (§7.2)."""

    recipient_id: UUID


class DirectConversationResponse(BaseModel):
    """Chat existente o temporal sin persistir (§7.2, Q20, Q146)."""

    conversation_id: UUID | None = None
    is_temporary: bool = True
    conversation: ConversationSummary | None = None
    recipient: UserSummary


class CreateGroupBody(BaseModel):
    """Cuerpo de `POST /api/conversations/groups` (§7.3, Q87–Q89)."""

    name: str = Field(min_length=3, max_length=40)
    member_ids: list[UUID] = Field(default_factory=list)


class RenameGroupBody(BaseModel):
    """Cuerpo de `PATCH /api/conversations/{id}` (§7.5, Q87)."""

    name: str = Field(min_length=3, max_length=40)


class AddMemberBody(BaseModel):
    """Cuerpo de `POST /api/conversations/{id}/members` (§7.6)."""

    user_id: UUID


class LeaveBody(BaseModel):
    """Cuerpo de `POST /api/conversations/{id}/leave` (§7.8)."""

    mode: Literal["keep_history", "hide"] = "keep_history"


class LeaveResponse(BaseModel):
    """Resultado de la salida: archivo y nuevo administrador (§7.8)."""

    archived: bool
    new_admin_id: UUID | None = None


class PreferencesBody(BaseModel):
    """Cuerpo de `PUT /api/conversations/{id}/preferences` (§7.9)."""

    hidden: bool
