"""Contenedor y mensajes reutilizables de las pantallas de autenticación.

Solo presentación: las reglas y mensajes viven en `state/auth_state.py`,
que las pantallas declaran como handlers de los formularios.
"""

import reflex as rx

from Chatly.state.auth_state import AuthState


def auth_shell(title: str, subtitle: str = "", *content: rx.Component) -> rx.Component:
    """Tarjeta centrada común a las pantallas de auth (login, registro, etc.)."""
    return rx.center(
        rx.card(
            rx.vstack(
                rx.vstack(
                    rx.badge("Chatly", variant="solid", color_scheme="blue", size="2"),
                    rx.heading(title, size="7", weight="bold", text_align="center"),
                    rx.cond(
                        subtitle != "",
                        rx.text(
                            subtitle,
                            size="2",
                            color_scheme="gray",
                            text_align="center",
                        ),
                        rx.fragment(),
                    ),
                    spacing="2",
                    align="center",
                    width="100%",
                ),
                rx.vstack(*content, spacing="5", width="100%", align="center"),
                rx.divider(margin_top="0.5rem"),
                rx.text(
                    "Chatly · aplicación de demostración",
                    size="1",
                    color_scheme="gray",
                    text_align="center",
                ),
                spacing="5",
                align="center",
                width="100%",
            ),
            size="4",
            variant="classic",
            width="100%",
            max_width="440px",
        ),
        width="100%",
        min_height="100vh",
        padding="1.5rem",
        background="radial-gradient(120% 120% at 50% 0%, var(--accent-2), var(--gray-1))",
    )


def form_alert() -> rx.Component:
    """Aviso rojo para el error general del formulario, si lo hay."""
    return rx.cond(
        AuthState.error_message != "",
        rx.callout(
            AuthState.error_message,
            icon="triangle_alert",
            color_scheme="red",
            width="100%",
        ),
        rx.fragment(),
    )


def info_banner() -> rx.Component:
    """Aviso de información (confirmación enviada, contraseña cambiada, etc.)."""
    return rx.cond(
        AuthState.info_message != "",
        rx.callout(
            AuthState.info_message,
            icon="info",
            color_scheme="grass",
            width="100%",
        ),
        rx.fragment(),
    )


def field_label(text: str) -> rx.Component:
    """Etiqueta de campo de formulario, alineada a la izquierda."""
    return rx.text(text, size="2", weight="medium", width="100%")


def field_error(message: rx.Var[str]) -> rx.Component:
    """Mensaje de error bajo un campo; solo se muestra si el mensaje no está vacío.

    `message` es la var de estado con el texto del error (por ejemplo
    `AuthState.error_email`).
    """
    return rx.cond(
        message != "",
        rx.text(
            message,
            size="1",
            color_scheme="red",
        ),
        rx.fragment(),
    )


def submit_button(label: str) -> rx.Component:
    """Botón de envío con estado de carga; va dentro de `rx.form`."""
    return rx.button(
        label,
        type="submit",
        size="3",
        width="100%",
        margin_top="0.25rem",
        loading=AuthState.is_loading,
    )
