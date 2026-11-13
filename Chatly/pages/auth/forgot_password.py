"""Página de solicitud del enlace de recuperación de contraseña.

Invoca `POST /api/auth/forgot-password` con `fetch`; la respuesta es `202`
siempre — nunca revela si el correo está registrado (§4.6).
"""

import reflex as rx

from Chatly.components.auth_shell import (
    auth_shell,
    field_error,
    form_alert,
    info_banner,
    submit_button,
)
from Chatly.state.auth_state import AuthState


def forgot_password_page() -> rx.Component:
    """Formulario para pedir el enlace de recuperación."""
    return auth_shell(
        "Recupera tu contraseña",
        "Te enviaremos un enlace para crear una contraseña nueva.",
        rx.form(
            rx.vstack(
                form_alert(),
                info_banner(),
                rx.vstack(
                    rx.input(
                        placeholder="Correo electrónico",
                        type="email",
                        value=AuthState.email,
                        on_change=AuthState.set_email,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="email",
                        autocomplete="email",
                    ),
                    field_error(AuthState.error_email),
                    spacing="2",
                    width="100%",
                ),
                submit_button("Enviar enlace de recuperación"),
                spacing="4",
                width="100%",
            ),
            on_submit=AuthState.handle_forgot,
            no_validate=True,
            width="100%",
        ),
        rx.link("Volver a iniciar sesión", href="/login", size="2"),
    )
