"""Página de inicio de sesión.

Invoca `POST /api/auth/login` con `fetch` del navegador (vía `AuthState`
y `rx.call_script`): la respuesta HTTP es la única forma de fijar las
cookies HttpOnly `chatly_at`/`chatly_rt` (docs/architecture.md §5.3).
Tras el éxito la guarda de `/` resuelve la sesión desde la cookie.
"""

import reflex as rx

from Chatly.components.auth_shell import (
    auth_shell,
    field_error,
    field_label,
    form_alert,
    submit_button,
)
from Chatly.state.auth_state import AuthState


def login_page() -> rx.Component:
    """Formulario de acceso de Chatly."""
    return auth_shell(
        "Inicia sesión",
        "Entra con tu correo y contraseña para chatear.",
        rx.form(
            rx.vstack(
                form_alert(),
                rx.vstack(
                    field_label("Correo electrónico"),
                    rx.input(
                        placeholder="tu@correo.com",
                        type="email",
                        value=AuthState.email,
                        on_change=AuthState.set_email,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="email",
                        autocomplete="email",
                    ),
                    field_error("email"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Contraseña"),
                    rx.input(
                        placeholder="Tu contraseña",
                        type="password",
                        value=AuthState.password,
                        on_change=AuthState.set_password,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="password",
                        autocomplete="current-password",
                    ),
                    field_error("password"),
                    spacing="2",
                    width="100%",
                ),
                submit_button("Entrar"),
                spacing="4",
                width="100%",
            ),
            on_submit=AuthState.handle_login,
            width="100%",
        ),
        rx.link(
            "¿No tienes cuenta? Crear una",
            href="/register",
            size="2",
        ),
        rx.link(
            "¿Olvidaste tu contraseña?",
            href="/forgot-password",
            size="2",
        ),
    )
