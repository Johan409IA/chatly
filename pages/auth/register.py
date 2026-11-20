"""Página de registro: asistente de cinco pasos.

Diseño de referencia `assets/ux-ui/`: nombre → correo y alias → contraseña →
fecha y género → intereses. El avance es interactivo: «Siguiente» solo se
habilita cuando lo que hay en pantalla está completo, y al pulsar se pasa al
siguiente paso (también con la tecla Enter dentro del formulario).

El backend no cambia: al final se envía el mismo `POST /api/auth/register`
con todos los datos (Q15: el alta no inicia sesión; el flujo termina en
`/verify-pending`). Los intereses son opcionales (Q117, Q178) y el catálogo
se carga desde el servidor (`AuthState.load_interests`).
"""

import reflex as rx

from Chatly.components.auth_layout import (
    auth_alert,
    auth_split,
    field_block,
    progress_dots,
)
from Chatly.state.auth_state import (
    MAX_INTERESTS,
    REGISTER_STEPS,
    AuthState,
    InterestCategory,
    InterestItem,
)

# Icono de cada interés del catálogo (nombre del seed → icono de Lucide).
_INTEREST_ICONS: dict[str, str] = {
    "Programación": "code",
    "IA": "brain_circuit",
    "Ciberseguridad": "shield_check",
    "Desarrollo web": "monitor",
    "Marketing": "megaphone",
    "Ventas": "trending_up",
    "Emprendimiento": "briefcase",
    "UI/UX": "app_window",
    "Diseño gráfico": "palette",
    "Ilustración": "pencil",
    "Música": "music",
    "Cine": "clapperboard",
    "Videojuegos": "gamepad_2",
    "Fútbol": "goal",
    "Baloncesto": "volleyball",
    "Fitness": "dumbbell",
}


def _icon(name: rx.Var[str]) -> rx.Component:
    """Icono estático del interés según su nombre en el catálogo."""
    options = sorted(_INTEREST_ICONS.items())
    icon = rx.icon(
        options[-1][1],
        size=20,
        class_name="chatly-auth__interest-icon",
    )
    for label, tag in reversed(options[:-1]):
        icon = rx.cond(
            name == label,
            rx.icon(tag, size=20, class_name="chatly-auth__interest-icon"),
            icon,
        )
    return icon


def _step_header(number: int, question: str) -> rx.Component:
    """Número del paso (en grande) y la pregunta que responde ese paso."""
    return rx.box(
        rx.text(str(number), class_name="chatly-auth__step-number"),
        rx.text(question, class_name="chatly-auth__question"),
        class_name="chatly-auth__row",
    )


def _text_input(
    placeholder: str,
    value: rx.Var[str],
    on_change: rx.EventHandler,
    name: str,
    icon: str = "",
    input_type: str = "text",
) -> rx.Component:
    """Campo de texto con icono opcional a la izquierda."""
    control = rx.input(
        placeholder=placeholder,
        type=input_type,
        value=value,
        on_change=on_change,
        width="100%",
        size="3",
        variant="surface",
        name=name,
    )
    if not icon:
        return rx.box(control, class_name="chatly-auth__control chatly-auth__control--plain")
    return rx.box(
        rx.icon(icon, size=18, class_name="chatly-auth__icon"),
        control,
        class_name="chatly-auth__control",
    )


def _step_name() -> rx.Component:
    """Paso 1: nombre completo."""
    return rx.box(
        _step_header(1, "¿Cuál es tu nombre completo?"),
        field_block(
            "Tu nombre",
            _text_input(
                "Tu Nombre",
                AuthState.display_name,
                AuthState.set_display_name,
                "display_name",
            ),
            hint="Escribe tu nombre para empezar a conectar",
            error=AuthState.error_display_name,
        ),
        class_name="chatly-auth__stack chatly-auth__stack--wide",
    )


def _step_contact() -> rx.Component:
    """Paso 2: correo electrónico y alias."""
    return rx.box(
        _step_header(2, "¿Cómo quieres que te encuentren?"),
        field_block(
            "Correo electrónico",
            _text_input(
                "tu@correo.com",
                AuthState.email,
                AuthState.set_email,
                "email",
                icon="at_sign",
                input_type="email",
            ),
            error=AuthState.error_email,
        ),
        field_block(
            "Alias único",
            _text_input(
                "johan_dev",
                AuthState.alias,
                AuthState.set_alias,
                "alias",
                icon="hash",
            ),
            hint="3–20 caracteres, empieza por una letra",
            error=AuthState.error_alias,
        ),
        class_name="chatly-auth__stack chatly-auth__stack--wide",
    )


def _step_password() -> rx.Component:
    """Paso 3: contraseña y su repetición."""
    return rx.box(
        _step_header(3, "Elige una contraseña fuerte"),
        field_block(
            "Contraseña (mínimo 8 caracteres)",
            _text_input(
                "Tu contraseña",
                AuthState.password,
                AuthState.set_password,
                "password",
                icon="lock",
                input_type="password",
            ),
            error=AuthState.error_password,
        ),
        field_block(
            "Repite la contraseña",
            _text_input(
                "La misma contraseña",
                AuthState.password_confirm,
                AuthState.set_password_confirm,
                "password_confirm",
                icon="lock",
                input_type="password",
            ),
            error=AuthState.error_password_confirm,
        ),
        rx.text(
            "Usa letras, números y símbolos para mayor seguridad",
            class_name="chatly-auth__hint",
        ),
        class_name="chatly-auth__stack chatly-auth__stack--wide",
    )


def _gender_card(value: str, label: str, icon: str) -> rx.Component:
    """Tarjeta de género (solo masculino y femenino)."""
    selected = AuthState.gender == value
    return rx.box(
        rx.icon(icon, size=28, class_name="chatly-auth__gender-icon"),
        rx.text(label, size="2"),
        class_name=rx.cond(
            selected,
            "chatly-auth__gender chatly-auth__gender--on",
            "chatly-auth__gender",
        ),
        on_click=AuthState.set_gender(value),
        role="button",
        tab_index=0,
    )


def _step_profile() -> rx.Component:
    """Paso 4: fecha de nacimiento y género."""
    return rx.box(
        _step_header(4, "¡Casi listo! Completa tu perfil"),
        field_block(
            "Fecha de nacimiento",
            _text_input(
                "",
                AuthState.birth_date,
                AuthState.set_birth_date,
                "birth_date",
                input_type="date",
            ),
            hint="Escribe tu fecha para continuar",
            error=AuthState.error_birth_date,
        ),
        rx.box(
            _gender_card("masculino", "Masculino", "mars_stroke"),
            _gender_card("femenino", "Femenino", "venus"),
            class_name="chatly-auth__genders",
        ),
        rx.text("Selecciona tu género", class_name="chatly-auth__hint"),
        rx.cond(
            AuthState.error_gender != "",
            rx.text(AuthState.error_gender, class_name="chatly-auth__error"),
            rx.fragment(),
        ),
        class_name="chatly-auth__stack chatly-auth__stack--wide",
    )


def _interest_card(interest: rx.Var[InterestItem]) -> rx.Component:
    """Tarjeta clicable de un interés; resaltada si está seleccionada."""
    selected = AuthState.selected_interest_ids.contains(interest.id)
    return rx.box(
        _icon(interest.name),
        rx.text(interest.name, size="1"),
        class_name=rx.cond(
            selected,
            "chatly-auth__interest chatly-auth__interest--on",
            "chatly-auth__interest",
        ),
        on_click=AuthState.toggle_interest(interest.id),
        role="button",
        tab_index=0,
    )


def _interest_category(category: rx.Var[InterestCategory]) -> rx.Component:
    """Categoría del catálogo con sus intereses."""
    return rx.box(
        rx.text(category.name, class_name="chatly-auth__category-name"),
        rx.box(
            rx.foreach(category.interests, _interest_card),
            class_name="chatly-auth__interest-list",
        ),
    )


def _step_interests() -> rx.Component:
    """Paso 5: intereses (opcional)."""
    return rx.box(
        rx.box(
            rx.text("Intereses (opcional)", class_name="chatly-auth__label"),
            rx.spacer(),
            rx.text(
                f"{AuthState.selected_interests_count}/{MAX_INTERESTS}",
                class_name="chatly-auth__counter",
            ),
            class_name="chatly-auth__row",
        ),
        rx.text(
            "Elige hasta 10 intereses para encontrar personas con tus mismos temas.",
            class_name="chatly-auth__hint",
        ),
        rx.cond(
            AuthState.interest_message != "",
            rx.text(AuthState.interest_message, class_name="chatly-auth__error"),
            rx.fragment(),
        ),
        rx.box(
            rx.foreach(AuthState.interest_catalog, _interest_category),
            class_name="chatly-auth__interests",
        ),
        rx.text(
            "Puedes omitirlos y configurarlos después desde tu perfil.",
            class_name="chatly-auth__hint",
        ),
        class_name="chatly-auth__stack",
    )


def _step_actions() -> rx.Component:
    """Botón principal («Siguiente» / «Crear cuenta») y vuelta atrás.

    El botón nunca se deshabilita: al pulsarlo se valida el paso y, si falta
    algo, se muestra el error bajo el campo (así también funciona la tecla
    Enter, que el navegador no envía si el botón está deshabilitado).
    """
    return rx.box(
        rx.cond(
            AuthState.is_last_step,
            rx.button(
                "Crear cuenta",
                type="submit",
                class_name="chatly-auth__pill",
                loading=AuthState.is_loading,
            ),
            rx.button(
                "Siguiente",
                type="submit",
                class_name=rx.cond(
                    AuthState.can_advance,
                    "chatly-auth__pill chatly-auth__pill--ready",
                    "chatly-auth__pill",
                ),
            ),
        ),
        rx.cond(
            AuthState.register_step > 1,
            rx.button(
                "Atrás",
                type="button",
                on_click=AuthState.prev_step,
                class_name="chatly-auth__back",
            ),
            rx.fragment(),
        ),
        class_name="chatly-auth__stack chatly-auth__stack--tight",
    )


def register_page() -> rx.Component:
    """Asistente de alta de Chatly."""
    return auth_split(
        rx.cond(
            AuthState.is_last_step,
            rx.heading(
                "Dinos qué te interesa",
                class_name="chatly-auth__title chatly-auth__title--sentence",
            ),
            rx.heading(
                "Crea tu cuenta en Chatly",
                class_name="chatly-auth__title",
            ),
        ),
        rx.cond(
            AuthState.is_last_step,
            rx.text(
                "Último paso: elige los temas sobre los que quieres charlar.",
                class_name="chatly-auth__subtitle",
            ),
            rx.text(
                "Unos pasos y tu cuenta lista para chatear.",
                class_name="chatly-auth__subtitle",
            ),
        ),
        progress_dots(REGISTER_STEPS, AuthState.register_step),
        rx.form(
            rx.box(
                auth_alert(AuthState.error_message),
                rx.cond(AuthState.register_step == 1, _step_name(), rx.fragment()),
                rx.cond(AuthState.register_step == 2, _step_contact(), rx.fragment()),
                rx.cond(AuthState.register_step == 3, _step_password(), rx.fragment()),
                rx.cond(AuthState.register_step == 4, _step_profile(), rx.fragment()),
                rx.cond(AuthState.register_step == 5, _step_interests(), rx.fragment()),
                _step_actions(),
                class_name="chatly-auth__stack chatly-auth__stack--wide",
            ),
            on_submit=AuthState.handle_register_step,
            no_validate=True,
            width="100%",
        ),
        rx.link(
            "¿Ya tienes cuenta? Inicia sesión",
            href="/login",
            class_name="chatly-auth__link",
        ),
    )
