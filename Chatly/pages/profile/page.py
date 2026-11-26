"""Pantalla de perfil propio: datos, intereses y visibilidad (Iteración 2).

Completa las tareas pendientes del roadmap: modificar intereses con el
contador `N/10` y activar/desactivar la visibilidad pública desde los
ajustes. El correo se muestra solo lectura (nunca se edita desde aquí).
"""

import reflex as rx

from Chatly.state.auth_state import InterestCategory, InterestItem
from Chatly.state.profile_state import ProfileState


def _field(
    label: str,
    control: rx.Component,
    hint: str = "",
    error: rx.Var[str] | str = "",
) -> rx.Component:
    """Bloque de campo con etiqueta, pista y error opcional."""
    return rx.box(
        rx.text(label, class_name="chatly-profile__label"),
        control,
        rx.cond(
            error != "",
            rx.text(error, class_name="chatly-profile__error"),
            rx.fragment(),
        ),
        rx.cond(
            hint != "",
            rx.text(hint, class_name="chatly-profile__hint"),
            rx.fragment(),
        ),
        class_name="chatly-profile__field",
    )


def _identity_row() -> rx.Component:
    """Correo (solo lectura) y estado de verificación."""
    return rx.hstack(
        rx.icon("at_sign", size=16, class_name="chatly-profile__identity-icon"),
        rx.text(ProfileState.email, class_name="chatly-profile__email"),
        rx.badge(
            ProfileState.email_verified_text,
            color_scheme=rx.cond(ProfileState.email_verified, "green", "orange"),
            variant="soft",
            size="1",
        ),
        class_name="chatly-profile__identity",
        align="center",
        spacing="2",
        width="100%",
    )


def _data_section() -> rx.Component:
    """Tarjeta de datos editables del perfil."""
    return rx.box(
        rx.heading("Datos del perfil", size="4", class_name="chatly-profile__section-title"),
        _identity_row(),
        rx.form(
            _field(
                "Tu nombre",
                rx.input(
                    placeholder="Tu Nombre",
                    value=ProfileState.edit_display_name,
                    on_change=ProfileState.set_edit_display_name,
                    width="100%",
                    size="2",
                    variant="surface",
                ),
                error=ProfileState.error_display_name,
            ),
            _field(
                "Alias único",
                rx.input(
                    placeholder="tu_alias",
                    value=ProfileState.edit_alias,
                    on_change=ProfileState.set_edit_alias,
                    width="100%",
                    size="2",
                    variant="surface",
                    disabled=~ProfileState.can_change_alias,
                ),
                hint=ProfileState.alias_hint,
                error=ProfileState.error_alias,
            ),
            _field(
                "Fecha de nacimiento",
                rx.input(
                    type="date",
                    value=ProfileState.edit_birth_date,
                    on_change=ProfileState.set_edit_birth_date,
                    width="100%",
                    size="2",
                    variant="surface",
                ),
                hint=f"Tienes {ProfileState.age} años.",
                error=ProfileState.error_birth_date,
            ),
            _field(
                "Género",
                rx.select(
                    ["femenino", "masculino"],
                    value=ProfileState.edit_gender,
                    on_change=ProfileState.set_edit_gender,
                    width="100%",
                    size="2",
                    placeholder="Selecciona tu género",
                ),
            ),
            rx.button(
                "Guardar cambios",
                type="submit",
                size="2",
                loading=ProfileState.is_saving_profile,
                class_name="chatly-profile__submit",
            ),
            on_submit=ProfileState.save_profile,
            no_validate=True,
            width="100%",
        ),
        class_name="chatly-profile__card",
    )


def _interest_chip(interest: rx.Var[InterestItem]) -> rx.Component:
    """Etiqueta seleccionable de un interés del catálogo."""
    selected = ProfileState.selected_interest_ids.contains(interest.id)
    return rx.button(
        interest.name,
        type="button",
        class_name=rx.cond(
            selected,
            "chatly-profile__chip chatly-profile__chip--on",
            "chatly-profile__chip",
        ),
        on_click=ProfileState.toggle_interest(interest.id),
    )


def _interest_category(category: rx.Var[InterestCategory]) -> rx.Component:
    """Categoría del catálogo con sus intereses como etiquetas."""
    return rx.box(
        rx.text(category.name, class_name="chatly-profile__category-name"),
        rx.box(
            rx.foreach(category.interests, _interest_chip),
            class_name="chatly-profile__chips",
        ),
        class_name="chatly-profile__category",
    )


def _interests_section() -> rx.Component:
    """Tarjeta de intereses con contador `N/10` y guardado completo."""
    return rx.box(
        rx.hstack(
            rx.heading("Tus intereses", size="4", class_name="chatly-profile__section-title"),
            rx.spacer(),
            rx.badge(
                ProfileState.interests_count_text,
                variant="soft",
                size="2",
                color_scheme="blue",
            ),
            width="100%",
            align="center",
        ),
        rx.text(
            "Elige hasta 10 intereses: con ellos te encuentran las personas "
            "y los grupos con tus mismos temas.",
            class_name="chatly-profile__hint",
        ),
        rx.cond(
            ProfileState.interest_message != "",
            rx.text(
                ProfileState.interest_message,
                class_name=rx.cond(
                    ProfileState.interest_message.contains("actualizados"),
                    "chatly-profile__message",
                    "chatly-profile__error",
                ),
            ),
            rx.fragment(),
        ),
        rx.box(
            rx.foreach(ProfileState.interest_catalog, _interest_category),
            class_name="chatly-profile__catalog",
        ),
        rx.button(
            "Guardar intereses",
            type="button",
            size="2",
            loading=ProfileState.is_saving_interests,
            on_click=ProfileState.save_interests,
            class_name="chatly-profile__submit",
        ),
        class_name="chatly-profile__card",
    )


def _visibility_section() -> rx.Component:
    """Tarjeta de ajustes de visibilidad pública (Q116, Q139, Q165)."""
    return rx.box(
        rx.heading("Ajustes de visibilidad", size="4", class_name="chatly-profile__section-title"),
        rx.hstack(
            rx.vstack(
                rx.text("Perfil público", size="2", weight="medium"),
                rx.text(
                    "Con la visibilidad activada, tu nombre, fotografía e intereses "
                    "pueden aparecer en las recomendaciones de Descubrir. Si la "
                    "desactivas, dejas de aparecer en sugerencias y tus intereses "
                    "dejan de verse, pero te pueden seguir encontrando con la "
                    "búsqueda directa. Los grupos que administras no cambian.",
                    size="1",
                    class_name="chatly-profile__hint",
                ),
                align="start",
                spacing="1",
                flex="1",
            ),
            rx.switch(
                checked=ProfileState.is_public,
                on_change=ProfileState.set_visibility,
                disabled=ProfileState.is_saving_visibility,
                aria_label="Perfil público",
            ),
            width="100%",
            align="start",
            spacing="4",
        ),
        class_name="chatly-profile__card",
    )


def profile_page() -> rx.Component:
    """Perfil propio: datos, intereses y visibilidad."""
    return rx.box(
        rx.box(
            rx.box(
                rx.link(
                    rx.hstack(
                        rx.icon("chevron_left", size=18),
                        rx.text("Volver a los chats"),
                        class_name="chatly-profile__back-inner",
                        align="center",
                        spacing="1",
                    ),
                    href="/conversations",
                    class_name="chatly-profile__back",
                ),
                rx.heading("Tu perfil", size="6", class_name="chatly-profile__title"),
                class_name="chatly-profile__topbar",
            ),
            rx.cond(
                ProfileState.is_loading,
                rx.center(
                    rx.spinner(size="3"),
                    class_name="chatly-profile__status",
                ),
                rx.vstack(
                    rx.cond(
                        ProfileState.profile_error != "",
                        rx.callout(
                            ProfileState.profile_error,
                            icon="triangle_alert",
                            color_scheme="red",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        ProfileState.profile_message != "",
                        rx.callout(
                            ProfileState.profile_message,
                            icon="circle_check",
                            color_scheme="green",
                            size="1",
                        ),
                        rx.fragment(),
                    ),
                    _data_section(),
                    _interests_section(),
                    _visibility_section(),
                    spacing="4",
                    width="100%",
                ),
            ),
            class_name="chatly-profile__inner",
        ),
        class_name="chatly-profile",
    )
