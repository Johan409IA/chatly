from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    is_discoverable: bool = False  # constante: su columna llega en 0013
    description: str | None = None  # constante: su columna llega en 0013


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total_unread: int = 0  # suma de no leídos, no el conteo de hilos


# ---------- Cuerpos de petición ----------
class SendMessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    client_message_id: UUID | None = None
    reply_to_message_id: UUID | None = None


class SendMessageResponse(BaseModel):
    message: Message
    idempotent_replay: bool = False


class DirectMessageBody(BaseModel):
    recipient_id: UUID
    content: str = Field(min_length=1, max_length=4000)
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
