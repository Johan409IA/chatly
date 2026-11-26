"""Estado de la interfaz de conversaciones, alimentado por la API de Chatly."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

import reflex as rx

from Chatly.state.api_client import fetch_script, parse_response

_MAX_MESSAGE_LENGTH = 4000


@dataclass(frozen=True)
class ConversationItem:
    """Campos del resumen de conversación definido en el contrato de API."""

    id: str
    name: str
    initials: str
    avatar_url: str
    preview: str
    last_message_at: str
    unread_count: int
    members_count: int


@dataclass(frozen=True)
class MessageItem:
    """Campos del mensaje necesarios para mostrar el historial."""

    id: str
    author_id: str
    author_alias: str
    content: str
    created_at: str
    message_type: str
    deleted: bool
    reply_alias: str = ""
    reply_preview: str = ""


class ConversationState(rx.State):
    """Datos visibles de la lista y de la conversación seleccionada."""

    conversations: list[ConversationItem] = []
    messages: list[MessageItem] = []
    selected_conversation_id: str = ""
    selected_conversation_name: str = ""
    selected_conversation_initials: str = "CH"
    selected_conversation_avatar_url: str = ""
    selected_conversation_members_count: int = 0
    current_alias: str = ""
    current_display_name: str = ""
    current_avatar_url: str = ""
    profile_error: str = ""
    search_query: str = ""
    message_draft: str = ""
    list_error: str = ""
    messages_error: str = ""
    is_loading_conversations: bool = False
    is_loading_messages: bool = False
    is_loading_older: bool = False
    is_sending: bool = False
    total_unread: int = 0
    # Cursor de paginación hacia atrás (§8.1): (creado_en, id) del mensaje
    # más antiguo cargado; vacío cuando no hay más páginas.
    cursor_created_at: str = ""
    cursor_id: str = ""
    # Respuesta en curso (Q75): se muestra como chip sobre el compositor.
    reply_to_id: str = ""
    reply_to_alias: str = ""
    reply_to_preview: str = ""
    # Envío optimista: el texto se muestra con reloj mientras el servidor
    # responde; al confirmar se recarga el historial y aparece con ✓.
    pending_message: str = ""

    @rx.var
    def filtered_conversations(self) -> list[ConversationItem]:
        """Filtra localmente los resúmenes ya autorizados por el backend."""
        query = self.search_query.strip().casefold()
        if not query:
            return self.conversations
        return [
            conversation
            for conversation in self.conversations
            if query in conversation.name.casefold() or query in conversation.preview.casefold()
        ]

    @rx.var
    def has_filtered_conversations(self) -> bool:
        return bool(self.filtered_conversations)

    @rx.var
    def has_older_messages(self) -> bool:
        return self.cursor_id != ""

    @rx.var
    def can_send_message(self) -> bool:
        return (
            bool(self.message_draft.strip())
            and len(self.message_draft) <= _MAX_MESSAGE_LENGTH
            and not self.is_sending
        )

    @rx.var
    def draft_length(self) -> int:
        return len(self.message_draft)

    @rx.var
    def current_initials(self) -> str:
        name = self.current_display_name.strip() or self.current_alias.strip()
        return "".join(part[0] for part in name.split()[:2]).upper() or "CH"

    @rx.event
    def load_profile(self) -> rx.event.EventSpec:
        """Carga el nombre y el avatar del actor desde `GET /api/me`."""
        self.profile_error = ""
        return rx.call_script(
            fetch_script("/api/me"),
            callback=ConversationState.handle_profile_result,
        )

    @rx.event
    def handle_profile_result(self, result: Any) -> list[rx.event.EventSpec] | rx.event.EventSpec:
        status, body, _ = self._parse_response(result)
        if status != 200:
            self.profile_error = self._error_message(body, status)
            if status == 401:
                return rx.redirect("/login")
            return []
        alias = body.get("alias")
        display_name = body.get("display_name")
        if not isinstance(alias, str) or not isinstance(display_name, str):
            self.profile_error = "El servidor devolvió un perfil no válido."
            return []
        self.current_alias = alias
        self.current_display_name = display_name
        avatar_url = body.get("avatar_url")
        self.current_avatar_url = avatar_url if isinstance(avatar_url, str) else ""
        return []

    @rx.event
    def load_conversations(self) -> rx.event.EventSpec:
        """Carga la bandeja desde `GET /api/conversations`."""
        self.is_loading_conversations = True
        self.list_error = ""
        return rx.call_script(
            fetch_script("/api/conversations"),
            callback=ConversationState.handle_conversations_result,
        )

    @rx.event
    def handle_conversations_result(
        self, result: Any
    ) -> list[rx.event.EventSpec] | rx.event.EventSpec:
        self.is_loading_conversations = False
        status, body, _ = self._parse_response(result)
        if status != 200:
            self.list_error = self._error_message(body, status)
            if status == 401:
                return rx.redirect("/login")
            return []

        items = body.get("items")
        if not isinstance(items, list):
            self.list_error = "El servidor devolvió una lista de conversaciones no válida."
            return []

        parsed: list[ConversationItem] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                self.list_error = "El servidor devolvió una conversación no válida."
                return []
            parsed.append(
                ConversationItem(
                    id=str(item["id"]),
                    name=str(item.get("name") or "Conversación"),
                    initials=str(item.get("initials") or "CH"),
                    avatar_url=str(item.get("avatar_url") or ""),
                    preview=str(item.get("last_message_preview") or "Sin mensajes aún"),
                    last_message_at=self._format_time(str(item.get("last_message_at") or "")),
                    unread_count=self._int_value(item.get("unread_count")),
                    members_count=self._int_value(item.get("members_count")),
                )
            )

        self.conversations = parsed
        self.total_unread = self._int_value(body.get("total_unread"))
        selected = next(
            (
                conversation
                for conversation in parsed
                if conversation.id == self.selected_conversation_id
            ),
            None,
        )
        if selected is not None:
            self.selected_conversation_name = selected.name
            self.selected_conversation_initials = selected.initials
            self.selected_conversation_avatar_url = selected.avatar_url
            self.selected_conversation_members_count = selected.members_count
            return []
        self.selected_conversation_id = ""
        self.selected_conversation_name = ""
        self.selected_conversation_initials = "CH"
        self.selected_conversation_avatar_url = ""
        self.selected_conversation_members_count = 0
        self.messages = []
        return []

    @rx.event
    def select_conversation(self, conversation_id: str) -> rx.event.EventSpec | list:
        """Abre solo conversaciones que ya están en la respuesta del backend."""
        conversation = next(
            (item for item in self.conversations if item.id == conversation_id),
            None,
        )
        if conversation is None:
            return []
        return self._select_and_load(conversation)

    @rx.event
    def close_conversation(self) -> None:
        """Vuelve a la lista en pantallas pequeñas."""
        self.selected_conversation_id = ""
        self.selected_conversation_name = ""
        self.selected_conversation_initials = "CH"
        self.selected_conversation_avatar_url = ""
        self.selected_conversation_members_count = 0
        self.messages = []
        self.messages_error = ""
        self.cursor_created_at = ""
        self.cursor_id = ""
        self.cancel_reply()
        self.pending_message = ""

    @rx.event
    def load_messages(self) -> rx.event.EventSpec | list:
        """Recarga el historial de la conversación activa desde REST."""
        if not self.selected_conversation_id:
            return []
        self.is_loading_messages = True
        self.messages_error = ""
        self.cursor_created_at = ""
        self.cursor_id = ""
        path = (
            f"/api/conversations/{quote(self.selected_conversation_id, safe='')}/messages?limit=50"
        )
        return rx.call_script(
            fetch_script(path, request_id=self.selected_conversation_id),
            callback=ConversationState.handle_messages_result,
        )

    @rx.event
    def load_older_messages(self) -> rx.event.EventSpec | list:
        """Carga la página anterior con el cursor (§8.1, Q94)."""
        if not self.selected_conversation_id or not self.cursor_id:
            return []
        self.is_loading_older = True
        self.messages_error = ""
        path = (
            f"/api/conversations/{quote(self.selected_conversation_id, safe='')}/messages"
            f"?before_created_at={quote(self.cursor_created_at, safe='')}"
            f"&before_id={quote(self.cursor_id, safe='')}"
        )
        return rx.call_script(
            fetch_script(path, request_id=self.selected_conversation_id),
            callback=ConversationState.handle_older_result,
        )

    @rx.event
    def handle_older_result(self, result: Any) -> list[rx.event.EventSpec] | rx.event.EventSpec:
        """Antepone la página anterior al historial ya cargado."""
        status, body, request_id = parse_response(result)
        if request_id != self.selected_conversation_id:
            return []
        self.is_loading_older = False
        if status != 200:
            self.messages_error = self._error_message(body, status)
            if status == 401:
                return rx.redirect("/login")
            return []
        older, next_created_at, next_id = self._parse_message_page(body)
        if older is None:
            return []
        # La página anterior llega ordenada ascendente y va delante de todo.
        self.messages = older + self.messages
        self.cursor_created_at = next_created_at
        self.cursor_id = next_id
        return []

    @rx.event
    def handle_messages_result(self, result: Any) -> list[rx.event.EventSpec] | rx.event.EventSpec:
        status, body, request_id = parse_response(result)
        if request_id != self.selected_conversation_id:
            return []
        self.is_loading_messages = False
        if status != 200:
            self.messages_error = self._error_message(body, status)
            if status == 401:
                return rx.redirect("/login")
            return []

        parsed, next_created_at, next_id = self._parse_message_page(body)
        if parsed is None:
            self.messages_error = "El servidor devolvió un historial de mensajes no válido."
            return []
        self.messages = parsed
        self.cursor_created_at = next_created_at
        self.cursor_id = next_id
        return []

    @staticmethod
    def _parse_message_page(body: dict[str, Any]) -> tuple[list[MessageItem] | None, str, str]:
        """Convierte la respuesta §8.1 en items y el cursor de la página.

        Devuelve `(items, cursor_created_at, cursor_id)`; los items vacíos
        con `None` indican una respuesta malformada.
        """
        items = body.get("items")
        if not isinstance(items, list):
            return None, "", ""
        parsed: list[MessageItem] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                return None, "", ""
            author = item.get("author")
            if author is not None and not isinstance(author, dict):
                return None, "", ""
            poll = item.get("poll")
            content = item.get("content")
            if item.get("deleted"):
                display_content = "Se eliminó un mensaje"
            elif item.get("type") == "system":
                display_content = "Actualización de la conversación"
            elif item.get("type") == "poll":
                display_content = (
                    str(poll.get("question") or "Encuesta compartida")
                    if isinstance(poll, dict)
                    else "Encuesta compartida"
                )
            else:
                display_content = str(content or "")
            reply = item.get("reply_to")
            reply_alias = ""
            reply_preview = ""
            if isinstance(reply, dict):
                reply_alias = str(reply.get("author_alias") or "")
                raw_preview = str(reply.get("preview") or "")
                if item.get("deleted"):
                    reply_preview = "Se eliminó un mensaje"
                else:
                    reply_preview = raw_preview
            parsed.append(
                MessageItem(
                    id=str(item["id"]),
                    author_id=str(author.get("id") or "") if author else "",
                    author_alias=str(author.get("alias") or "") if author else "",
                    content=display_content,
                    created_at=ConversationState._format_time(str(item.get("created_at") or "")),
                    message_type=str(item.get("type") or "text"),
                    deleted=bool(item.get("deleted")),
                    reply_alias=reply_alias,
                    reply_preview=reply_preview,
                )
            )
        cursor = body.get("next_cursor")
        if isinstance(cursor, dict) and cursor.get("id"):
            return parsed, str(cursor.get("created_at") or ""), str(cursor["id"])
        return parsed, "", ""

    @rx.event
    def start_reply(self, message_id: str, alias: str, content: str) -> None:
        """Fija la respuesta en curso (Q75) para el chip del compositor."""
        self.reply_to_id = message_id
        self.reply_to_alias = alias
        preview = " ".join(content.split())
        self.reply_to_preview = preview[:80]

    @rx.event
    def cancel_reply(self) -> None:
        """Quita la respuesta en curso."""
        self.reply_to_id = ""
        self.reply_to_alias = ""
        self.reply_to_preview = ""

    @rx.event
    def send_message(self, _form_data: dict | None = None) -> rx.event.EventSpec | list:
        """Envía un texto y vuelve a leerlo del backend para mostrar el estado real."""
        content = self.message_draft.strip()
        if not self.selected_conversation_id:
            self.messages_error = "Selecciona una conversación para enviar un mensaje."
            return []
        if not content:
            self.messages_error = "Escribe un mensaje antes de enviarlo."
            return []
        if len(content) > _MAX_MESSAGE_LENGTH:
            self.messages_error = "El mensaje no puede superar los 4.000 caracteres."
            return []

        self.is_sending = True
        self.messages_error = ""
        # Envío optimista: burbuja propia con reloj hasta la confirmación.
        self.pending_message = content
        payload: dict[str, Any] = {
            "content": content,
            "client_message_id": "__GENERATE_UUID__",
        }
        if self.reply_to_id:
            payload["reply_to_message_id"] = self.reply_to_id
        path = f"/api/conversations/{quote(self.selected_conversation_id, safe='')}/messages"
        return rx.call_script(
            fetch_script(
                path,
                method="POST",
                payload=payload,
                request_id=self.selected_conversation_id,
            ).replace(
                json.dumps("__GENERATE_UUID__"),
                "crypto.randomUUID()",
            ),
            callback=ConversationState.handle_send_result,
        )

    @rx.event
    def handle_send_result(self, result: Any) -> list[rx.event.EventSpec] | rx.event.EventSpec:
        status, body, request_id = parse_response(result)
        if request_id != self.selected_conversation_id:
            return []
        self.is_sending = False
        self.pending_message = ""
        if status not in (200, 201):
            self.messages_error = self._error_message(body, status)
            if status == 401:
                return rx.redirect("/login")
            return []
        message = body.get("message")
        if not isinstance(message, dict) or not message.get("id"):
            self.messages_error = "El servidor no confirmó el mensaje enviado."
            return []
        self.message_draft = ""
        self.cancel_reply()
        return self.load_messages()

    @rx.event
    def set_search_query(self, value: str) -> None:
        self.search_query = value

    @rx.event
    def set_message_draft(self, value: str) -> None:
        self.message_draft = value

    def _select_and_load(self, conversation: ConversationItem) -> rx.event.EventSpec:
        self.selected_conversation_id = conversation.id
        self.selected_conversation_name = conversation.name
        self.selected_conversation_initials = conversation.initials
        self.selected_conversation_avatar_url = conversation.avatar_url
        self.selected_conversation_members_count = conversation.members_count
        self.messages = []
        self.messages_error = ""
        self.cursor_created_at = ""
        self.cursor_id = ""
        self.cancel_reply()
        self.pending_message = ""
        self.is_loading_messages = True
        path = f"/api/conversations/{quote(conversation.id, safe='')}/messages?limit=50"
        return rx.call_script(
            fetch_script(path, request_id=conversation.id),
            callback=ConversationState.handle_messages_result,
        )

    @staticmethod
    def _error_message(body: dict[str, Any], status: int) -> str:
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return str(error["message"])
        if status == 0:
            return (
                "No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo otra vez."
            )
        if status == 401:
            return "Tu sesión ha caducado. Inicia sesión de nuevo."
        if status == 403:
            return "No tienes permiso para consultar esta conversación."
        if status == 404:
            return "La conversación ya no está disponible."
        return "No se pudo completar la solicitud. Inténtalo otra vez."

    @staticmethod
    def _int_value(value: object) -> int:
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    @staticmethod
    def _format_time(value: str) -> str:
        if not value:
            return ""
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        if timestamp.tzinfo:
            return timestamp.astimezone().strftime("%H:%M")
        return timestamp.strftime("%H:%M")
