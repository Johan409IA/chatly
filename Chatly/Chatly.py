"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
from fastapi import FastAPI

from Chatly.backend.api.routes.health import router as health_router
from rxconfig import config


class State(rx.State):
    """The app state."""


def index() -> rx.Component:
    # Welcome, Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.text(
                "Get started by editing ",
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


api_app = FastAPI(title="Chatly API")
api_app.include_router(health_router)

app = rx.App(api_transformer=api_app)
app.add_page(index)
