"""Página de «confirmación de correo pendiente».

Tras el alta (Q15) el usuario no está autenticado: aquí se muestra el correo
del registro y se puede pedir el reenvío (`AuthState.handle_resend`, que
invoca `POST /api/auth/resend-verification` con `fetch` y responde `202`
siempre, sin revelar cuentas, §4.5).
"""

import reflex as rx

from Chatly.components.auth_shell import auth_shell, field_error, submit_button
from Chatly.state.auth_state import AuthState


def verify_pending_page() -> rx.Component:
    """Pantalla informativa con reenvío de confirmación."""
    return auth_shell(
        "Confirma tu correo",
        "",
        rx.callout(
            "Abre el enlace que te enviamos para activar tu cuenta. "
            "Si no lo ves, revisa la carpeta de spam o pide otro abajo.",
            icon="mail",
            color_scheme="blue",
            width="100%",
        ),
        rx.form(
            rx.vstack(
                rx.text("Correo del alta:", size="2", color_scheme="gray"),
                rx.text(
                    rx.cond(
                        AuthState.registered_email != "",
                        AuthState.registered_email,
                        "—",
                    ),
                    weight="medium",
                ),
                rx.vstack(
                    rx.input(
                        placeholder="Si cambió, escríbelo aquí",
                        type="email",
                        value=AuthState.email,
                        on_change=AuthState.set_email,
                        width="100%",
                        name="email",
                        autocomplete="email",
                    ),
                    field_error("email"),
                    spacing="3",
                    width="100%",
                ),
                submit_button("Reenviar correo de confirmación"),
                spacing="4",
                width="100%",
            ),
            on_submit=AuthState.handle_resend,
            width="100%",
        ),
        rx.link("Ya confirmé: ir a iniciar sesión", href="/login", size="2", margin_top="1rem"),
    )
