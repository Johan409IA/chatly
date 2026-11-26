"""Componentes de la bandeja y el historial de conversaciones."""

import reflex as rx

from Chatly.state.conversation_state import ConversationItem, ConversationState, MessageItem
from Chatly.state.session_state import SessionState


def _navigation_item(icon: str, label: str, active: bool = False, href: str = "") -> rx.Component:
    content = rx.vstack(
        rx.icon(icon, size=21),
        rx.text(label, class_name="chatly-chat__nav-label"),
        align="center",
        spacing="1",
    )
    if active or href:
        return rx.link(
            content,
            href=href or "/conversations",
            class_name=rx.cond(
                active,
                "chatly-chat__nav-item chatly-chat__nav-item--active",
                "chatly-chat__nav-item",
            ),
            aria_label=label,
        )
    return rx.button(
        content,
        class_name="chatly-chat__nav-item chatly-chat__nav-item--disabled",
        disabled=True,
        title=f"{label}: próximamente",
        aria_label=f"{label}, próximamente",
        variant="ghost",
        type="button",
    )


def _navigation_rail() -> rx.Component:
    return rx.box(
        rx.box(
            rx.image(
                src="/icons/chatly_logo.png",
                alt="Chatly",
                class_name="chatly-chat__rail-logo",
            ),
            class_name="chatly-chat__rail-brand",
            aria_label="Chatly",
        ),
        rx.vstack(
            _navigation_item("messages_square", "Chats", active=True),
            _navigation_item("users_round", "Comunidades"),
            _navigation_item("users", "Amigos"),
            _navigation_item("user_round", "Perfil", href="/profile"),
            _navigation_item("settings", "Ajustes"),
            class_name="chatly-chat__navigation",
            spacing="2",
            width="100%",
        ),
        class_name="chatly-chat__rail",
    )


def _avatar(initials: rx.Var[str], avatar_url: rx.Var[str], size: str = "2.75rem") -> rx.Component:
    return rx.box(
        rx.cond(
            avatar_url != "",
            rx.image(
                src=avatar_url,
                alt="",
                width=size,
                height=size,
                object_fit="cover",
                border_radius="50%",
            ),
            rx.text(initials, class_name="chatly-chat__avatar-initials"),
        ),
        class_name="chatly-chat__avatar",
        width=size,
        height=size,
    )


def _conversation_row(conversation: ConversationItem) -> rx.Component:
    return rx.button(
        rx.hstack(
            _avatar(conversation.initials, conversation.avatar_url),
            rx.vstack(
                rx.hstack(
                    rx.text(
                        conversation.name,
                        class_name="chatly-chat__conversation-name",
                    ),
                    rx.spacer(),
                    rx.text(
                        conversation.last_message_at,
                        class_name="chatly-chat__conversation-time",
                    ),
                    width="100%",
                    align="center",
                ),
                rx.text(
                    conversation.preview,
                    class_name="chatly-chat__conversation-preview",
                    width="100%",
                ),
                spacing="1",
                align="start",
                min_width="0",
                flex="1",
            ),
            rx.cond(
                conversation.unread_count > 0,
                rx.badge(
                    conversation.unread_count,
                    class_name="chatly-chat__unread-badge",
                ),
                rx.fragment(),
            ),
            width="100%",
            align="center",
            spacing="3",
        ),
        on_click=ConversationState.select_conversation(conversation.id),
        class_name=rx.cond(
            conversation.id == ConversationState.selected_conversation_id,
            "chatly-chat__conversation chatly-chat__conversation--active",
            "chatly-chat__conversation",
        ),
        variant="ghost",
        width="100%",
        type="button",
    )


def _conversation_list() -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.image(
                src="/icons/chatly_logo.png",
                alt="Chatly",
                class_name="chatly-chat__brand-logo",
            ),
            rx.spacer(),
            rx.badge(
                ConversationState.total_unread,
                class_name="chatly-chat__total-unread",
            ),
            class_name="chatly-chat__sidebar-brand",
            align="center",
            width="100%",
        ),
        rx.text("Chats", class_name="chatly-chat__list-title"),
        rx.box(
            rx.icon("search", size=17),
            rx.input(
                value=ConversationState.search_query,
                on_change=ConversationState.set_search_query,
                placeholder="Buscar conversación",
                aria_label="Buscar conversación",
                class_name="chatly-chat__search-input",
            ),
            class_name="chatly-chat__search",
        ),
        rx.hstack(
            rx.text("MENSAJES", class_name="chatly-chat__section-label"),
            rx.spacer(),
            rx.button(
                rx.icon("refresh_cw", size=15),
                on_click=ConversationState.load_conversations,
                class_name="chatly-chat__refresh",
                variant="ghost",
                type="button",
                aria_label="Actualizar conversaciones",
            ),
            width="100%",
            align="center",
        ),
        rx.cond(
            ConversationState.is_loading_conversations,
            rx.center(rx.spinner(size="3"), class_name="chatly-chat__list-status"),
            rx.cond(
                ConversationState.list_error != "",
                rx.vstack(
                    rx.callout(
                        ConversationState.list_error,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="1",
                    ),
                    rx.button(
                        "Intentar de nuevo",
                        on_click=ConversationState.load_conversations,
                        variant="soft",
                        size="2",
                    ),
                    class_name="chatly-chat__list-status",
                    align="center",
                    width="100%",
                ),
                rx.cond(
                    ConversationState.has_filtered_conversations,
                    rx.vstack(
                        rx.foreach(
                            ConversationState.filtered_conversations,
                            _conversation_row,
                        ),
                        class_name="chatly-chat__conversation-list",
                        spacing="1",
                        width="100%",
                    ),
                    rx.center(
                        rx.vstack(
                            rx.icon("messages_square", size=28),
                            rx.text(
                                rx.cond(
                                    ConversationState.search_query != "",
                                    "No encontramos coincidencias",
                                    "Aún no tienes conversaciones",
                                ),
                                class_name="chatly-chat__empty-list-title",
                            ),
                            rx.text(
                                rx.cond(
                                    ConversationState.search_query != "",
                                    "Prueba con otro nombre.",
                                    "Cuando inicies un chat, aparecerá aquí.",
                                ),
                                class_name="chatly-chat__empty-list-copy",
                                text_align="center",
                            ),
                            spacing="2",
                            align="center",
                        ),
                        class_name="chatly-chat__list-status",
                    ),
                ),
            ),
        ),
        rx.box(
            _avatar(
                ConversationState.current_initials,
                ConversationState.current_avatar_url,
                "2rem",
            ),
            rx.vstack(
                rx.text(
                    rx.cond(
                        ConversationState.current_display_name != "",
                        ConversationState.current_display_name,
                        "Tu cuenta",
                    ),
                    class_name="chatly-chat__profile-name",
                ),
                rx.text(
                    rx.cond(
                        ConversationState.current_alias != "",
                        "@" + ConversationState.current_alias,
                        "Perfil",
                    ),
                    class_name="chatly-chat__profile-caption",
                ),
                align="start",
                spacing="0",
            ),
            rx.button(
                rx.icon("log_out", size=17),
                on_click=SessionState.logout,
                class_name="chatly-chat__logout",
                variant="ghost",
                type="button",
                disabled=SessionState.is_logging_out,
                aria_label="Cerrar sesión",
                title="Cerrar sesión",
            ),
            class_name="chatly-chat__profile",
        ),
        rx.cond(
            SessionState.logout_error != "",
            rx.text(
                SessionState.logout_error,
                class_name="chatly-chat__profile-error",
            ),
            rx.cond(
                ConversationState.profile_error != "",
                rx.text(
                    ConversationState.profile_error,
                    class_name="chatly-chat__profile-error",
                ),
                rx.fragment(),
            ),
        ),
        class_name="chatly-chat__sidebar",
    )


def _message(message: MessageItem) -> rx.Component:
    is_own_message = message.author_id == SessionState.actor_id
    return rx.hstack(
        rx.cond(
            message.message_type == "system",
            rx.text(
                message.content,
                class_name="chatly-chat__system-message",
                text_align="center",
            ),
            rx.vstack(
                rx.cond(
                    (message.reply_alias != "") | (message.reply_preview != ""),
                    rx.vstack(
                        rx.text(
                            rx.cond(
                                message.reply_alias != "",
                                "Respondiendo a @" + message.reply_alias,
                                "Respondiendo",
                            ),
                            class_name="chatly-chat__reply-quote-author",
                        ),
                        rx.text(
                            message.reply_preview,
                            class_name="chatly-chat__reply-quote-preview",
                        ),
                        class_name="chatly-chat__reply-quote",
                        align="start",
                        spacing="0",
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    is_own_message | (message.author_alias == ""),
                    rx.fragment(),
                    rx.text(
                        "@" + message.author_alias,
                        class_name="chatly-chat__message-author",
                    ),
                ),
                rx.text(message.content, class_name="chatly-chat__message-content"),
                rx.hstack(
                    rx.text(message.created_at, class_name="chatly-chat__message-time"),
                    rx.cond(
                        is_own_message,
                        rx.icon("check", size=13, class_name="chatly-chat__message-status"),
                        rx.fragment(),
                    ),
                    spacing="1",
                    align="center",
                ),
                class_name=rx.cond(
                    is_own_message,
                    "chatly-chat__message-bubble chatly-chat__message-bubble--own",
                    "chatly-chat__message-bubble",
                ),
                align=rx.cond(is_own_message, "end", "start"),
                spacing="1",
            ),
        ),
        rx.cond(
            (message.message_type == "text") & (~message.deleted),
            rx.tooltip(
                rx.button(
                    rx.icon("corner_up_left", size=15),
                    on_click=ConversationState.start_reply(
                        message.id, message.author_alias, message.content
                    ),
                    class_name="chatly-chat__message-action",
                    variant="ghost",
                    type="button",
                    aria_label="Responder a este mensaje",
                ),
                content="Responder",
            ),
            rx.fragment(),
        ),
        class_name=rx.cond(
            message.message_type == "system",
            "chatly-chat__message-row chatly-chat__message-row--system",
            rx.cond(
                is_own_message,
                "chatly-chat__message-row chatly-chat__message-row--own",
                "chatly-chat__message-row",
            ),
        ),
        width="100%",
        align="center",
        spacing="2",
    )


def _pending_bubble() -> rx.Component:
    """Envío optimista: burbuja propia con reloj hasta la confirmación."""
    return rx.cond(
        ConversationState.pending_message != "",
        rx.box(
            rx.vstack(
                rx.text(
                    ConversationState.pending_message,
                    class_name="chatly-chat__message-content",
                ),
                rx.hstack(
                    rx.icon("clock", size=12, class_name="chatly-chat__message-pending"),
                    rx.text(
                        "Enviando…",
                        class_name="chatly-chat__message-pending",
                    ),
                    spacing="1",
                    align="center",
                ),
                class_name=(
                    "chatly-chat__message-bubble chatly-chat__message-bubble--own"
                    " chatly-chat__message-bubble--pending"
                ),
                align="end",
                spacing="1",
            ),
            class_name="chatly-chat__message-row chatly-chat__message-row--own",
            width="100%",
        ),
        rx.fragment(),
    )


def _load_older_button() -> rx.Component:
    """Paginación hacia atrás: los 30 mensajes anteriores (Q94)."""
    return rx.cond(
        ConversationState.has_older_messages,
        rx.center(
            rx.button(
                rx.cond(
                    ConversationState.is_loading_older,
                    rx.spinner(size="2"),
                    "Cargar mensajes anteriores",
                ),
                on_click=ConversationState.load_older_messages,
                class_name="chatly-chat__load-older",
                variant="ghost",
                type="button",
                disabled=ConversationState.is_loading_older,
            ),
            width="100%",
        ),
        rx.fragment(),
    )


def _reply_chip() -> rx.Component:
    """Chip de la respuesta en curso sobre el compositor (Q75)."""
    return rx.cond(
        ConversationState.reply_to_id != "",
        rx.hstack(
            rx.icon("corner_up_left", size=15, class_name="chatly-chat__reply-chip-icon"),
            rx.vstack(
                rx.text(
                    rx.cond(
                        ConversationState.reply_to_alias != "",
                        "Respondiendo a @" + ConversationState.reply_to_alias,
                        "Respondiendo",
                    ),
                    class_name="chatly-chat__reply-chip-author",
                ),
                rx.text(
                    ConversationState.reply_to_preview,
                    class_name="chatly-chat__reply-chip-preview",
                ),
                align="start",
                spacing="0",
                min_width="0",
            ),
            rx.spacer(),
            rx.button(
                rx.icon("x", size=15),
                on_click=ConversationState.cancel_reply,
                class_name="chatly-chat__reply-chip-cancel",
                variant="ghost",
                type="button",
                aria_label="Cancelar respuesta",
            ),
            class_name="chatly-chat__reply-chip",
            width="100%",
            align="center",
            spacing="3",
        ),
        rx.fragment(),
    )


def _empty_conversation() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.box(
                rx.icon("messages_square", size=30),
                class_name="chatly-chat__welcome-icon",
            ),
            rx.heading("Tu espacio para conversar", size="5"),
            rx.text(
                "Selecciona una conversación para ver los mensajes.",
                class_name="chatly-chat__welcome-copy",
                text_align="center",
            ),
            align="center",
            spacing="3",
        ),
        class_name="chatly-chat__welcome",
    )


def _active_conversation() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.icon("chevron_left", size=20),
                on_click=ConversationState.close_conversation,
                class_name="chatly-chat__back",
                variant="ghost",
                type="button",
                aria_label="Volver a conversaciones",
            ),
            _avatar(
                ConversationState.selected_conversation_initials,
                ConversationState.selected_conversation_avatar_url,
            ),
            rx.vstack(
                rx.text(
                    ConversationState.selected_conversation_name,
                    class_name="chatly-chat__active-name",
                ),
                rx.text(
                    "Conversación de Chatly",
                    class_name="chatly-chat__active-caption",
                ),
                align="start",
                spacing="0",
            ),
            class_name="chatly-chat__conversation-header",
            align="center",
            width="100%",
        ),
        rx.cond(
            ConversationState.is_loading_messages,
            rx.center(rx.spinner(size="3"), class_name="chatly-chat__messages-status"),
            rx.cond(
                ConversationState.messages_error != "",
                rx.center(
                    rx.vstack(
                        rx.callout(
                            ConversationState.messages_error,
                            icon="triangle_alert",
                            color_scheme="red",
                            size="2",
                        ),
                        rx.button(
                            "Volver a intentar",
                            on_click=ConversationState.load_messages,
                            variant="soft",
                            size="2",
                        ),
                        align="center",
                    ),
                    class_name="chatly-chat__messages-status",
                ),
                rx.cond(
                    ConversationState.messages.length() > 0,
                    rx.vstack(
                        _load_older_button(),
                        rx.foreach(ConversationState.messages, _message),
                        _pending_bubble(),
                        class_name="chatly-chat__messages",
                        spacing="3",
                        width="100%",
                    ),
                    rx.center(
                        rx.vstack(
                            rx.icon("message_circle", size=24),
                            rx.text("Todavía no hay mensajes"),
                            rx.text(
                                "Envía el primero para iniciar la conversación.",
                                class_name="chatly-chat__welcome-copy",
                                text_align="center",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        class_name="chatly-chat__messages-status",
                    ),
                ),
            ),
        ),
        rx.form(
            _reply_chip(),
            rx.hstack(
                rx.text_area(
                    value=ConversationState.message_draft,
                    on_change=ConversationState.set_message_draft,
                    placeholder="Escribe un mensaje…",
                    max_length=4000,
                    class_name="chatly-chat__composer-input",
                    resize="none",
                    name="content",
                ),
                rx.button(
                    rx.icon("send", size=18),
                    type="submit",
                    loading=ConversationState.is_sending,
                    disabled=~ConversationState.can_send_message,
                    class_name="chatly-chat__send",
                    aria_label="Enviar mensaje",
                ),
                class_name="chatly-chat__composer",
                align="end",
                spacing="3",
            ),
            rx.hstack(
                rx.text("Los mensajes se guardan en la conversación."),
                rx.spacer(),
                rx.text(
                    ConversationState.draft_length,
                    "/4000",
                ),
                class_name="chatly-chat__composer-hint",
                width="100%",
            ),
            on_submit=ConversationState.send_message,
            no_validate=True,
            class_name="chatly-chat__composer-form",
            width="100%",
        ),
        class_name="chatly-chat__conversation-panel",
        spacing="0",
        width="100%",
    )


def _conversation_info() -> rx.Component:
    return rx.box(
        rx.text("Información", class_name="chatly-chat__info-title"),
        rx.cond(
            ConversationState.selected_conversation_id != "",
            rx.vstack(
                _avatar(
                    ConversationState.selected_conversation_initials,
                    ConversationState.selected_conversation_avatar_url,
                    "5.5rem",
                ),
                rx.text(
                    ConversationState.selected_conversation_name,
                    class_name="chatly-chat__info-name",
                ),
                rx.cond(
                    ConversationState.selected_conversation_members_count > 0,
                    rx.text(
                        ConversationState.selected_conversation_members_count,
                        " integrantes",
                        class_name="chatly-chat__info-count",
                    ),
                    rx.fragment(),
                ),
                rx.box(
                    rx.text("Detalles", class_name="chatly-chat__info-section-title"),
                    rx.text(
                        "La lista de integrantes y la descripción aparecerán aquí "
                        "cuando estén disponibles en el servidor.",
                        class_name="chatly-chat__info-copy",
                    ),
                    class_name="chatly-chat__info-card",
                ),
                class_name="chatly-chat__info-content",
                align="center",
                spacing="3",
                width="100%",
            ),
            rx.text(
                "Selecciona un chat para ver su información.",
                class_name="chatly-chat__info-copy",
            ),
        ),
        class_name="chatly-chat__info",
    )


def chat_interface() -> rx.Component:
    """Interfaz principal; no incluye contenido simulado."""
    return rx.box(
        _navigation_rail(),
        _conversation_list(),
        rx.box(
            rx.cond(
                ConversationState.selected_conversation_id != "",
                _active_conversation(),
                _empty_conversation(),
            ),
            class_name="chatly-chat__main",
        ),
        _conversation_info(),
        class_name=rx.cond(
            ConversationState.selected_conversation_id != "",
            "chatly-chat chatly-chat--conversation-open",
            "chatly-chat",
        ),
    )
