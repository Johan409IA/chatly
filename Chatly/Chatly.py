"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from Chatly.backend.api.routes.health import router as health_router
from Chatly.backend.core.errors import (
    DomainError,
    domain_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from Chatly.backend.core.logging import configure_logging
from Chatly.backend.core.settings import get_settings
from Chatly.pages.auth.login import login_page
from Chatly.state.session_state import SessionState
from rxconfig import config

# El logging JSON se configura antes de crear la app;
# así ningún evento posterior queda sin redacción.
configure_logging(get_settings().log_level)


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    # Welcome, Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Bienvenido a chatly!", size="9"),
            rx.text(
                "Empieza a chatear ",
                rx.code(f"{config.app_name}/{config.app_name}.py"),
                size="5",
            ),
            rx.link(
                rx.button("Check out our docs!"),
                href="https://reflex.dev/docs/getting-started/introduction/",
                is_external=True,
            ),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


api_app = FastAPI(
    title="Chatly API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
api_app.include_router(health_router)
api_app.add_exception_handler(DomainError, domain_error_handler)
api_app.add_exception_handler(RequestValidationError, validation_exception_handler)
api_app.add_exception_handler(Exception, unhandled_exception_handler)

app = rx.App(api_transformer=api_app)
# Página protegida: sin sesión válida, la guarda redirige a /login.
app.add_page(index, on_load=[SessionState.guard_page])
app.add_page(login_page, route="/login", on_load=[SessionState.redirect_if_authenticated])
