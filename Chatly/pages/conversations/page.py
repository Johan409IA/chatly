"""Página principal de conversaciones."""

import reflex as rx

from Chatly.components.chat.chat_interface import chat_interface


def conversations_page() -> rx.Component:
    return chat_interface()
