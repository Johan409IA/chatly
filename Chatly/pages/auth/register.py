"""Página de registro de cuenta nueva.

Invoca `POST /api/auth/register` con `fetch` del navegador; el registro no
inicia sesión (Q15): tras un alta exitosa el flujo termina en
`/verify-pending`. La validación de cliente (`AuthState.validate_register`)
duplica la del servidor del contrato §4.1; la respuesta authoritative es la
del backend.

El bloque de intereses es opcional (Q117, Q178): el catálogo se carga desde
el servidor (`AuthState.load_interests`) y la selección viaja en
`interest_ids`.
"""

import reflex as rx

from Chatly.components.auth_shell import (
    auth_shell,
    field_error,
    field_label,
    form_alert,
    submit_button,
)
from Chatly.state.auth_state import (
    GENDER_OPTIONS,
    MAX_INTERESTS,
    AuthState,
    InterestCategory,
    InterestItem,
)


def _interest_badge(interest: rx.Var[InterestItem]) -> rx.Component:
    """Etiqueta clicable de un interés; sólida si está seleccionada."""
    is_selected = AuthState.selected_interest_ids.contains(interest.id)
    return rx.cond(
        is_selected,
        rx.badge(
            interest.name,
            variant="solid",
            color_scheme="blue",
            on_click=AuthState.toggle_interest(interest.id),
            cursor="pointer",
            role="button",
            tab_index=0,
        ),
        rx.badge(
            interest.name,
            variant="outline",
            color_scheme="blue",
            on_click=AuthState.toggle_interest(interest.id),
            cursor="pointer",
            role="button",
            tab_index=0,
        ),
    )


def _interest_category(category: rx.Var[InterestCategory]) -> rx.Component:
    """Sección del accordion con los intereses de una categoría."""
    return rx.accordion.item(
        value=category.id,
        header=category.name,
        content=rx.flex(
            rx.foreach(category.interests, _interest_badge),
            wrap="wrap",
            gap="2",
            align="center",
            width="100%",
        ),
        width="100%",
    )


def interests_block() -> rx.Component:
    """Bloque opcional «Intereses (opcional)» del registro."""
    return rx.vstack(
        field_label("Intereses (opcional)"),
        rx.hstack(
            rx.text(
                "Elige hasta 10 intereses para encontrar personas con tus mismos temas.",
                size="1",
                color_scheme="gray",
            ),
            rx.spacer(),
            rx.text(
                f"{AuthState.selected_interests_count}/{MAX_INTERESTS}",
                size="2",
                weight="medium",
            ),
            align="center",
            width="100%",
        ),
        rx.cond(
            AuthState.interest_message != "",
            rx.callout(
                AuthState.interest_message,
                icon="triangle_alert",
                color_scheme="orange",
                width="100%",
            ),
            rx.fragment(),
        ),
        rx.accordion.root(
            rx.foreach(AuthState.interest_catalog, _interest_category),
            type="multiple",
            width="100%",
        ),
        rx.text(
            "Puedes omitirlos y configurarlos después desde tu perfil.",
            size="1",
            color_scheme="gray",
        ),
        spacing="2",
        width="100%",
    )


def register_page() -> rx.Component:
    """Formulario de alta de Chatly."""
    return auth_shell(
        "Crea tu cuenta",
        "Unos datos y tu correo; luego confirmarás el registro por email.",
        rx.form(
            rx.vstack(
                form_alert(),
                rx.vstack(
                    field_label("Correo electrónico"),
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
                    field_error("email"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Contraseña"),
                    rx.input(
                        placeholder="Mín. 8, una mayúscula y un símbolo",
                        type="password",
                        value=AuthState.password,
                        on_change=AuthState.set_password,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="password",
                        autocomplete="new-password",
                    ),
                    field_error("password"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Repite la contraseña"),
                    rx.input(
                        placeholder="La misma contraseña",
                        type="password",
                        value=AuthState.password_confirm,
                        on_change=AuthState.set_password_confirm,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="password_confirm",
                        autocomplete="new-password",
                    ),
                    field_error("password_confirm"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Alias"),
                    rx.input(
                        placeholder="Único, 3–20, ej. johan_dev",
                        value=AuthState.alias,
                        on_change=AuthState.set_alias,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="alias",
                    ),
                    field_error("alias"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Tu nombre"),
                    rx.input(
                        placeholder="Entre 2 y 60 caracteres",
                        value=AuthState.display_name,
                        on_change=AuthState.set_display_name,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="display_name",
                    ),
                    field_error("display_name"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Fecha de nacimiento"),
                    rx.input(
                        type="date",
                        value=AuthState.birth_date,
                        on_change=AuthState.set_birth_date,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="birth_date",
                    ),
                    field_error("birth_date"),
                    spacing="2",
                    width="100%",
                ),
                rx.vstack(
                    field_label("Género"),
                    rx.select(
                        list(GENDER_OPTIONS),
                        placeholder="Elige una opción",
                        default_value="",
                        value=AuthState.gender,
                        on_change=AuthState.set_gender,
                        width="100%",
                        size="3",
                        variant="surface",
                        name="gender",
                    ),
                    field_error("gender"),
                    spacing="2",
                    width="100%",
                ),
                interests_block(),
                submit_button("Crear cuenta"),
                spacing="4",
                width="100%",
            ),
            on_submit=AuthState.handle_register,
            width="100%",
        ),
        rx.link("¿Ya tienes cuenta? Inicia sesión", href="/login", size="2"),
    )
