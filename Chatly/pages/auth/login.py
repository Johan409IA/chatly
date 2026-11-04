"""Página de inicio de sesión (provisional).

Las pantallas completas de registro, login, confirmación y recuperación se
construyen en la tarea de pantallas de la Iteración 2. Esta página existe
para que las guardas de sesión tengan a dónde redirigir.
"""

import reflex as rx


def login_page() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Inicia sesión", size="7"),
            rx.text("La pantalla de inicio de sesión está en construcción."),
            spacing="4",
            justify="center",
            min_height="85vh",
        ),
    )
