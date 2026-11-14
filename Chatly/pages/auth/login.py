"""Página de inicio de sesión.

Invoca `POST /api/auth/login` con `fetch` del navegador (vía `AuthState`
y `rx.call_script`): la respuesta HTTP es la única forma de fijar las
cookies HttpOnly `chatly_at`/`chatly_rt` (docs/architecture.md §5.3).
Tras el éxito la guarda de `/` resuelve la sesión desde la cookie.

El diseño (panel de marca con la red de nodos y panel oscuro con el
formulario) vive en `components/auth_layout.py`.
"""

import reflex as rx

from Chatly.components.auth_layout import auth_alert, auth_split, field_block
from Chatly.state.auth_state import AuthState


def _email_field() -> rx.Component:
    """Campo de correo con el icono «@» a la izquierda."""
    return field_block(
        "Correo electrónico",
        rx.box(
            rx.icon("at_sign", size=18, class_name="chatly-auth__icon"),
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
            class_name="chatly-auth__control",
        ),
        error=AuthState.error_email,
    )


def _password_field() -> rx.Component:
    """Campo de contraseña con el icono del candado."""
    return field_block(
        "Tu contraseña",
        rx.box(
            rx.icon("lock", size=18, class_name="chatly-auth__icon"),
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
            class_name="chatly-auth__control",
        ),
        error=AuthState.error_password,
    )


def login_page() -> rx.Component:
    """Formulario de acceso de Chatly."""
    return auth_split(
        rx.heading("Inicia sesión en Chatly", class_name="chatly-auth__title"),
        rx.text(
            "Entra con tu correo y contraseña para chatear.",
            class_name="chatly-auth__subtitle",
        ),
        rx.box(
            rx.icon("shield_check", size=54),
            class_name="chatly-auth__emblem",
        ),
        rx.form(
            rx.box(
                auth_alert(AuthState.error_message),
                _email_field(),
                _password_field(),
                rx.button(
                    "Entrar",
                    type="submit",
                    class_name="chatly-auth__button",
                    loading=AuthState.is_loading,
                ),
                class_name="chatly-auth__stack chatly-auth__stack--wide",
            ),
            on_submit=AuthState.handle_login,
            no_validate=True,
            width="100%",
        ),
        rx.link(
            "¿No tienes cuenta? Crear una",
            href="/register",
            class_name="chatly-auth__link",
        ),
        rx.link(
            "¿Olvidaste tu contraseña?",
            href="/forgot-password",
            class_name="chatly-auth__link",
        ),
        rx.box(class_name="chatly-auth__separator"),
        rx.text(
            "Chatly · aplicación de demostración",
            class_name="chatly-auth__footer",
        ),
    )
