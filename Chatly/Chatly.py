"""Aplicación Chatly: rutas, API y guardas de sesión."""

import reflex as rx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from Chatly.backend.api.routes.auth import router as auth_router
from Chatly.backend.api.routes.health import router as health_router
from Chatly.backend.api.routes.interests import router as interests_router
from Chatly.backend.core.errors import (
    DomainError,
    domain_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from Chatly.backend.core.logging import configure_logging
from Chatly.backend.core.settings import get_settings
from Chatly.pages.auth.confirm import confirm_page
from Chatly.pages.auth.forgot_password import forgot_password_page
from Chatly.pages.auth.login import login_page
from Chatly.pages.auth.register import register_page
from Chatly.pages.auth.reset_password import reset_password_page
from Chatly.pages.auth.verify_pending import verify_pending_page
from Chatly.state.auth_state import AuthState
from Chatly.state.session_state import SessionState

# El logging JSON se configura antes de crear la app;
# así ningún evento posterior queda sin redacción.
configure_logging(get_settings().log_level)


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    """Pantalla de bienvenida tras iniciar sesión (protegida por guarda)."""
    return rx.center(
        rx.vstack(
            rx.badge("Chatly", variant="solid", color_scheme="blue", size="2"),
            rx.heading("Bienvenido a Chatly", size="8", weight="bold", text_align="center"),
            spacing="4",
            align="center",
        ),
        width="100%",
        min_height="100vh",
        padding="1.5rem",
        background="radial-gradient(120% 120% at 50% 0%, var(--accent-2), var(--gray-1))",
    )


api_app = FastAPI(
    title="Chatly API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
# El navegador llama al API en otro puerto (:8000 desde :3000): sin CORS con
# credenciales el `fetch` se rechaza y las cookies HttpOnly se descartan.
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
api_app.include_router(health_router)
api_app.include_router(auth_router)
api_app.include_router(interests_router)
api_app.add_exception_handler(DomainError, domain_error_handler)
api_app.add_exception_handler(RequestValidationError, validation_exception_handler)
api_app.add_exception_handler(Exception, unhandled_exception_handler)

app = rx.App(api_transformer=api_app)
# Página protegida: sin sesión válida, la guarda redirige a /login.
app.add_page(index, on_load=[SessionState.guard_page])
# Pantallas de autenticación (públicas; login redirige si ya hay sesión).
app.add_page(login_page, route="/login", on_load=[SessionState.redirect_if_authenticated])
app.add_page(
    register_page,
    route="/register",
    on_load=[SessionState.redirect_if_authenticated, AuthState.load_interests],
)
app.add_page(
    verify_pending_page, route="/verify-pending", on_load=[SessionState.redirect_if_authenticated]
)
app.add_page(
    forgot_password_page,
    route="/forgot-password",
    on_load=[SessionState.redirect_if_authenticated],
)
app.add_page(reset_password_page, route="/reset-password")
app.add_page(confirm_page, route="/auth/confirm", on_load=[AuthState.handle_confirm])
