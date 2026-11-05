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
                    rx.input(
                        placeholder="Correo electrónico",
                        type="email",
                        value=AuthState.email,
                        on_change=AuthState.set_email,
                        width="100%",
                        name="email",
                        autocomplete="email",
                    ),
                    field_error("email"),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.input(
                        placeholder="Contraseña",
                        type="password",
                        value=AuthState.password,
                        on_change=AuthState.set_password,
                        width="100%",
                        name="password",
                        autocomplete="current-password",
                    ),
                    field_error("password"),
                    spacing="4",
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
            margin_top="1rem",
        ),
        rx.link(
            "¿Olvidaste tu contraseña?",
            href="/forgot-password",
            size="2",
        ),
    )
