"""Página de nueva contraseña tras la recuperación.

El correo de Supabase llega aquí con el fragmento `#token` (acordado con el
equipo, §4.7): `AuthState.handle_reset` invoca `POST /api/auth/reset-password`
con `fetch` y tras `204` lleva a login con la contraseña ya cambiada.
Si el enlace no trae token, se avisa sin revelar detalles del enlace.
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


def reset_password_page() -> rx.Component:
    """Formulario de nueva contraseña."""
    return auth_shell(
        "Nueva contraseña",
        "Elige una contraseña fuerte para tu cuenta.",
        rx.form(
            rx.vstack(
                form_alert(),
                info_banner(),
                rx.vstack(
                    rx.input(
                        placeholder="Contraseña nueva",
                        type="password",
                        value=AuthState.password,
                        on_change=AuthState.set_password,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="password",
                        autocomplete="new-password",
                    ),
                    field_error(AuthState.error_password),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    rx.input(
                        placeholder="Repite la contraseña",
                        type="password",
                        value=AuthState.password_confirm,
                        on_change=AuthState.set_password_confirm,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="password_confirm",
                        autocomplete="new-password",
                    ),
                    field_error(AuthState.error_password_confirm),
                    spacing="2",
                    width="100%",
                ),
                submit_button("Guardar contraseña"),
                spacing="4",
                width="100%",
            ),
            on_submit=AuthState.handle_reset,
            no_validate=True,
            width="100%",
        ),
        rx.link("Volver a iniciar sesión", href="/login", size="2"),
    )
