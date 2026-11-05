"""Página de registro de cuenta nueva.

Invoca `POST /api/auth/register` con `fetch` del navegador; el registro no
inicia sesión (Q15): tras un alta exitosa el flujo termina en
`/verify-pending`. La validación de cliente (`AuthState.validate_register`)
duplica la del servidor del contrato §4.1; la respuesta authoritative es la
del backend.
"""

import reflex as rx

from Chatly.components.auth_shell import (
    auth_shell,
    field_error,
    form_alert,
    submit_button,
)
from Chatly.state.auth_state import GENDER_OPTIONS, AuthState


def register_page() -> rx.Component:
    """Formulario de alta de Chatly."""
    return auth_shell(
        "Crea tu cuenta",
        "Unos datos y tu correo; luego confirmarás el registro por email.",
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
                        autocomplete="new-password",
                    ),
                    field_error("password"),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.input(
                        placeholder="Repite la contraseña",
                        type="password",
                        value=AuthState.password_confirm,
                        on_change=AuthState.set_password_confirm,
                        width="100%",
                        name="password_confirm",
                        autocomplete="new-password",
                    ),
                    field_error("password_confirm"),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.input(
                        placeholder="Alias (único, 3–20, ej. johan_dev)",
                        value=AuthState.alias,
                        on_change=AuthState.set_alias,
                        width="100%",
                        name="alias",
                    ),
                    field_error("alias"),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.input(
                        placeholder="Tu nombre (2–60 caracteres)",
                        value=AuthState.display_name,
                        on_change=AuthState.set_display_name,
                        width="100%",
                        name="display_name",
                    ),
                    field_error("display_name"),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.input(
                        type="date",
                        value=AuthState.birth_date,
                        on_change=AuthState.set_birth_date,
                        width="100%",
                        name="birth_date",
                    ),
                    field_error("birth_date"),
                    spacing="4",
                    width="100%",
                ),
                rx.vstack(
                    rx.select(
                        list(GENDER_OPTIONS),
                        placeholder="Género",
                        default_value="",
                        value=AuthState.gender,
                        on_change=AuthState.set_gender,
                        width="100%",
                        name="gender",
                    ),
                    field_error("gender"),
                    spacing="4",
                    width="100%",
                ),
                submit_button("Crear cuenta"),
                spacing="4",
                width="100%",
            ),
            on_submit=AuthState.handle_register,
            width="100%",
        ),
        rx.link("¿Ya tienes cuenta? Inicia sesión", href="/login", size="2", margin_top="1rem"),
    )
