"""Página de aterrizaje del enlace de confirmación.

El correo de Supabase llega con `?code=...`; el `on_load` de la ruta ejecuta
`AuthState.handle_confirm`, que incrementa `POST /api/auth/confirm` con
`fetch` (§4.8). La pantalla solo muestra el estado: procesando, éxito (que
redirige a login) o mensaje de error del enlace.
"""

import reflex as rx

from Chatly.components.auth_shell import auth_shell, form_alert, info_banner
from Chatly.state.auth_state import AuthState


def confirm_page() -> rx.Component:
    """Confirmación de correo en curso."""
    return auth_shell(
        "Confirmando tu correo",
        "",
        rx.cond(
            AuthState.is_loading,
            rx.hstack(
                rx.spinner(size="3"),
                rx.text("Confirmando tu correo, un momento…", size="2"),
                spacing="3",
            ),
            rx.fragment(),
        ),
        form_alert(),
        info_banner(),
        rx.link("Ir a iniciar sesión", href="/login", size="2", margin_top="1rem"),
    )
