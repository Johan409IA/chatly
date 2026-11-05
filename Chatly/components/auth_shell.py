"""Contenedor y mensajes reutilizables de las pantallas de autenticación.

Solo presentación: las reglas y mensajes viven en `state/auth_state.py`,
que las pantallas declaran como handlers de los formularios.
"""

import reflex as rx

from Chatly.state.auth_state import AuthState


def auth_shell(title: str, subtitle: str = "", *content: rx.Component) -> rx.Component:
    """Tarjeta centrada común a las pantallas de auth (login, registro, etc.)."""
    header = [rx.heading(title, size="6", margin_bottom="0.5rem")]
    if subtitle:
        header.append(
            rx.text(
                subtitle,
                size="2",
                color_scheme="gray",
                text_align="center",
                margin_bottom="1.5rem",
            )
        )
    return rx.container(
        rx.vstack(
            rx.vstack(
                rx.badge("Chatly", variant="solid", color_scheme="blue"),
                rx.vstack(
                    rx.heading(title, size="6"),
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
                    margin_bottom="1.25rem",
                ),
                *content,
                spacing="4",
                width="100%",
            ),
            rx.text(
                "Chatly · aplicación de demostración",
                size="1",
                color_scheme="gray",
                margin_top="1.5rem",
            ),
            justify="center",
            min_height="100vh",
            padding="1.5rem",
        ),
        max_width="440px",
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


def field_error(field: str) -> rx.Component:
    """Mensaje de error bajo un campo; solo se muestra con la clave dada.

    `field` es la clave literal del dict `AuthState.field_errors`,
    por ejemplo «email» o «password».
    """
    return rx.cond(
        AuthState.field_errors[field] != "",
        rx.text(
            AuthState.field_errors[field],
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
        width="100%",
        loading=AuthState.is_loading,
    )
