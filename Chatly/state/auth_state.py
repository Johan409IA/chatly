"""Estado de autenticación de las pantallas de auth.

Los endpoints reales están en `backend/api/routes/auth.py` (§4 del contrato)
y fijan las cookies HttpOnly `chatly_at`/`chatly_rt`. Como las cookies solo
se fijan en una respuesta HTTP real, TODAS las llamadas de estas pantallas
se hacen con `fetch` desde el navegador vía `rx.call_script` — nunca como
eventos de Reflex (WebSocket), que no son respuestas HTTP y no fijan cookies.

Tras un login/reset/confirm exitoso el navegador ya tiene la cookie, así que
el callback solo redirige: `SessionState.guard_page` / `redirect_if_authenticated`
resuelven la sesión leyendo y verificando el JWT desde la cookie (identidad
siempre del token, nunca del cliente).

Validadores y mensajes en español (duplicación deliberada del lado cliente).
El registro no inicia sesión (Q15): tras un alta exitosa el flujo termina
en `/verify-pending`.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import reflex as rx

from Chatly.backend.core.settings import get_settings
from Chatly.backend.repositories.interest_repository import get_interest_repository

logger = logging.getLogger(__name__)

GENDER_OPTIONS = ("femenino", "masculino")

# Máximo de intereses personales (Q124); el mismo límite valida el backend.
MAX_INTERESTS = 10

# Pasos del asistente de registro (diseño `assets/ux-ui/`):
# 1 nombre, 2 correo y alias, 3 contraseña, 4 fecha y género, 5 intereses.
REGISTER_STEPS = 5

# Paso al que vuelve el usuario cuando el backend rechaza un dato:
# el error se muestra en la pantalla donde está el campo que hay que corregir.
_ERROR_STEP: dict[str, int] = {
    "email_already_registered": 2,
    "alias_taken": 2,
    "weak_password": 3,
    "validation_error": 1,
    "interest_limit_exceeded": 5,
}

# El frontend (:3000) y el API (:8000) son orígenes distintos en desarrollo;
# `fetch` relativo iría al servidor de Vite. Vacío = mismo origen (producción).
_API_BASE = get_settings().api_public_url.rstrip("/")

# alias: 3–20, empieza por letra, luego [a-z0-9_] (api-contracts.md, registro).
_ALIAS_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_BIRTH_MIN_AGE = 18
_BIRTH_MAX_AGE = 120
_BIRTH_ERROR = "Debes tener entre 18 y 120 años."

_ERROR_TEXTS = {
    "email_already_registered": (
        "Este correo ya está registrado. Inicia sesión o recupera tu contraseña."
    ),
    "alias_taken": "Ese alias ya está en uso. Elige otro.",
    "weak_password": "La contraseña no cumple las reglas.",
    "email_not_verified": "Confirma tu correo para poder entrar.",
    "invalid_credentials": "Correo o contraseña incorrectos.",
    "unauthorized": "El enlace no es válido o ha caducado.",
    "rate_limited": "Demasiados intentos. Espera unos minutos y prueba de nuevo.",
    "interest_limit_exceeded": "Puedes elegir hasta 10 intereses.",
    "validation_error": "Revisa los datos del formulario.",
}

_GENERIC_ERRORS = {
    401: "Correo o contraseña incorrectos.",
    403: "No tienes permiso para esta acción.",
    404: "El enlace no es válido o ha caducado.",
    409: "No se pudo completar: los datos entran en conflicto.",
    422: "Revisa los datos del formulario.",
    429: "Demasiados intentos. Espera unos minutos.",
    500: "Ocurrió un error en el servidor. Inténtalo de nuevo.",
    503: "El servicio de cuentas no está disponible. Inténtalo de nuevo.",
}

_NETWORK_ERROR = "No hay conexión. Inténtalo de nuevo."
_UNEXPECTED_ERROR = "Ocurrió un error inesperado. Inténtalo de nuevo."


def normalized_email(value: str) -> str:
    """Correo sin espacios y en minúsculas (api-contracts.md:202)."""
    return value.strip().lower()


def normalized_alias(value: str) -> str:
    """Alias sin espacios y en minúsculas; la unicidad ignora mayúsculas (Q57)."""
    return value.strip().lower()


def calculate_age(birth_date: date, today: date | None = None) -> int:
    """Edad en años cumplidos; la fuente de verdad es `birth_date`."""
    today = today or date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def password_is_strong(value: str) -> bool:
    """Mínimo 8, una mayúscula, una minúscula y un símbolo; el número es opcional."""
    if len(value) < 8:
        return False
    has_upper = any(character.isupper() for character in value)
    has_lower = any(character.islower() for character in value)
    has_symbol = any(not character.isalnum() for character in value)
    return has_upper and has_lower and has_symbol


def validate_register(
    email: str,
    password: str,
    password_confirm: str,
    alias: str,
    display_name: str,
    birth_date: date | None,
    gender: str,
    today: date | None = None,
) -> dict[str, str]:
    """Validación de cliente del registro; devuelve «campo: mensaje» en español."""
    errors: dict[str, str] = {}
    if not _EMAIL_RE.fullmatch(normalized_email(email)):
        errors["email"] = "Escribe un correo válido."
    if not password_is_strong(password):
        errors["password"] = (
            "La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un símbolo."
        )
    if password_confirm != password or not password_confirm:
        errors["password_confirm"] = "Las contraseñas no coinciden."
    if not _ALIAS_RE.fullmatch(normalized_alias(alias)):
        errors["alias"] = (
            "El alias debe tener 3–20 caracteres: letra inicial y luego letras, números o _."
        )
    name = display_name.strip()
    if not 2 <= len(name) <= 60:
        errors["display_name"] = "El nombre debe tener entre 2 y 60 caracteres."
    if birth_date is None:
        errors["birth_date"] = _BIRTH_ERROR
    else:
        age = calculate_age(birth_date, today)
        if not _BIRTH_MIN_AGE <= age <= _BIRTH_MAX_AGE:
            errors["birth_date"] = _BIRTH_ERROR
    if gender not in GENDER_OPTIONS:
        errors["gender"] = "Elige una opción."
    return errors


def parse_birth_date(value: str) -> date:
    """Convierte «yyyy-mm-dd» (input date) en `date`; lanza ValueError si es inválida."""
    return date.fromisoformat(value.strip())


def name_error(display_name: str) -> str:
    """Mensaje de error del nombre completo; cadena vacía si el nombre es válido."""
    name = display_name.strip()
    if not name:
        return "Escribe tu nombre para empezar a conectar."
    if not 2 <= len(name) <= 60:
        return "El nombre debe tener entre 2 y 60 caracteres."
    return ""


# Plantilla de `fetch` que ejecuta el navegador (misma forma del contrato §4):
# POST con JSON, `credentials: "include"` (cookies HttpOnly cross-origin), y
# devolución como STRING JSON para que el resultado atraviese el puente de
# eventos sin ambigüedad.
#
# El script se evalúa con `eval` en el navegador, así que debe ser una
# EXPRESIÓN: por eso va entre paréntesis y se invoca al final (`(... )()`).
# Si fuera solo la función, `eval` devolvería la función, el callback
# recibiría un valor no serializable y el servidor recibiría el payload vacío.
_API_JS = (
    "const rawApi = '@API_BASE@';"
    "const apiBase = rawApi"
    "  ? (() => { const u = new URL(rawApi); u.hostname = window.location.hostname;"
    "      return u.origin; })()"
    "  : '';"
)

_FETCH_TEMPLATE = (
    "(async () => {" + _API_JS + 'const res = await fetch(apiBase + "@PATH@", {'
    'method: "POST",'
    'headers: {"Content-Type": "application/json"},'
    'credentials: "include",'
    "body: JSON.stringify(@PAYLOAD@),"
    "});"
    "const text = await res.text();"
    "let body = {};"
    "if (text) { try { body = JSON.parse(text); } catch (ignored) {} }"
    "return JSON.stringify({ status: res.status, body });"
    "})()"
)

# Confirmación: el enlace de Supabase puede traer `?token_hash=`, `?code=`
# (PKCE) o los tokens en el fragmento (flujo implícito). Se aceptan las tres.
_CONFIRM_TEMPLATE = (
    "(async () => {" + _API_JS + "const search = new URLSearchParams(window.location.search);"
    "const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));"
    "const tokenHash = search.get('token_hash') || hash.get('token_hash') || '';"
    "const code = search.get('code') || hash.get('code') || '';"
    "const already = Boolean(hash.get('access_token'));"
    "if (!tokenHash && !code) {"
    "  if (already) { return JSON.stringify({ status: 204, body: {}, already: true }); }"
    "  return JSON.stringify({"
    "    status: 400,"
    "    body: { error: { code: 'unauthorized' } },"
    "    already: false,"
    "  });"
    "}"
    'const res = await fetch(apiBase + "@CONFIRM_PATH@", {'
    'method: "POST",'
    'headers: {"Content-Type": "application/json"},'
    'credentials: "include",'
    "body: JSON.stringify({ token_hash: tokenHash, code: code }),"
    "});"
    "const text = await res.text();"
    "let body = {};"
    "if (text) { try { body = JSON.parse(text); } catch (ignored) {} }"
    "return JSON.stringify({ status: res.status, body, already: false });"
    "})()"
)


def _fetch_script(path: str, payload: Any) -> str:
    """Construye el script `fetch` de una llamada con el cuerpo dado.

    El payload se interpola con `json.dumps` (JS válido y seguro con
    comillas/símbolos). NUNCA registrar este string: contiene credenciales.
    """
    return (
        _FETCH_TEMPLATE.replace("@API_BASE@", _API_BASE)
        .replace("@PATH@", path)
        .replace("@PAYLOAD@", json.dumps(payload))
    )


@dataclass
class InterestItem:
    """Interés concreto del catálogo, listo para la interfaz."""

    id: str
    name: str


@dataclass
class InterestCategory:
    """Categoría del catálogo con los intereses que la componen."""

    id: str
    name: str
    interests: list[InterestItem] = field(default_factory=list)


class AuthState(rx.State):
    """Campos y eventos de las pantallas de autenticación."""

    # Campos de formulario compartidos por login, registro y recuperación.
    email: str = ""
    password: str = ""
    password_confirm: str = ""
    alias: str = ""
    display_name: str = ""
    birth_date: str = ""  # ISO «yyyy-mm-dd» tal como llega del input date.
    gender: str = ""

    # Catálogo de intereses y selección opcional del registro (Q117, Q178).
    interest_catalog: list[InterestCategory] = []
    selected_interest_ids: list[str] = []
    interest_message: str = ""

    # Paso actual del asistente de registro (1..REGISTER_STEPS).
    register_step: int = 1

    # Estados de UI que consumen las pantallas.
    is_loading: bool = False
    error_message: str = ""
    info_message: str = ""

    # Mensajes de error por campo. Son vars sueltas y no un dict: al leer
    # `state.dict["clave"]` en el cliente, la clave que no existe llega como
    # `undefined` y el mensaje no se pinta (bug de la 0.10.1).
    error_display_name: str = ""
    error_email: str = ""
    error_alias: str = ""
    error_password: str = ""
    error_password_confirm: str = ""
    error_birth_date: str = ""
    error_gender: str = ""

    # Correo del alta, para mostrarlo en «verificación pendiente» y reenvío.
    registered_email: str = ""

    @rx.var
    def selected_interests_count(self) -> int:
        """Cuántos intereses hay seleccionados ahora mismo (contador `N/10`)."""
        return len(self.selected_interest_ids)

    @rx.var
    def can_advance(self) -> bool:
        """El paso actual tiene los datos mínimos para pasar al siguiente."""
        return not self._step_errors(self.register_step)

    @rx.var
    def is_last_step(self) -> bool:
        """El asistente está en el paso final (el de los intereses)."""
        return self.register_step >= REGISTER_STEPS

    # ------------------------------------------------------------------
    # Setters de los inputs. Reflex 0.10 ya no genera `set_<campo>` solo
    # (`state_auto_setters=False`), así que se declaran explícitamente.
    # ------------------------------------------------------------------

    @rx.event
    def set_email(self, value: str) -> None:
        self.email = value
        self._clear_field_error("email")

    @rx.event
    def set_password(self, value: str) -> None:
        self.password = value
        self._clear_field_error("password")

    @rx.event
    def set_password_confirm(self, value: str) -> None:
        self.password_confirm = value
        self._clear_field_error("password_confirm")

    @rx.event
    def set_alias(self, value: str) -> None:
        self.alias = value
        self._clear_field_error("alias")

    @rx.event
    def set_display_name(self, value: str) -> None:
        self.display_name = value
        self._clear_field_error("display_name")

    @rx.event
    def set_birth_date(self, value: str) -> None:
        self.birth_date = value
        self._clear_field_error("birth_date")

    @rx.event
    def set_gender(self, value: str) -> None:
        self.gender = value
        self._clear_field_error("gender")

    # ------------------------------------------------------------------
    # Intereses (selección opcional del registro).
    # ------------------------------------------------------------------

    @rx.event
    async def load_interests(self) -> None:
        """Carga el catálogo público de intereses (una sola vez).

        El catálogo no necesita sesión ni cookies: se lee en el servidor con
        `app.catalogo_intereses()`, así que no usa `fetch` (esa regla aplica a
        las operaciones que fijan la sesión).
        """
        if self.interest_catalog:
            return
        try:
            catalog = await get_interest_repository().list_catalog()
        except Exception:  # pragma: no cover - depende del entorno
            logger.warning("No se pudo cargar el catálogo de intereses", exc_info=True)
            return
        self.interest_catalog = [
            InterestCategory(
                id=str(category.id),
                name=category.name,
                interests=[
                    InterestItem(id=str(interest.id), name=interest.name)
                    for interest in category.interests
                ],
            )
            for category in catalog
        ]

    @rx.event
    def toggle_interest(self, interest_id: str) -> None:
        """Añade o quita un interés de la selección; el máximo es 10 (Q124)."""
        if interest_id in self.selected_interest_ids:
            self.selected_interest_ids = [
                selected for selected in self.selected_interest_ids if selected != interest_id
            ]
            self.interest_message = ""
            return
        if len(self.selected_interest_ids) >= MAX_INTERESTS:
            self.interest_message = f"Puedes elegir hasta {MAX_INTERESTS} intereses."
            return
        self.selected_interest_ids = [*self.selected_interest_ids, interest_id]
        self.interest_message = ""

    # ------------------------------------------------------------------
    # Asistente de registro (pasos del diseño `assets/ux-ui/`).
    # ------------------------------------------------------------------

    @rx.event
    def next_step(self) -> None:
        """Avanza al siguiente paso; si falta algo, muestra el error del campo."""
        self._advance_step()

    @rx.event
    def prev_step(self) -> None:
        """Vuelve al paso anterior del asistente."""
        if self.register_step > 1:
            self.register_step -= 1
            self._set_field_errors({})

    @rx.event
    def reset_register(self) -> None:
        """Deja el asistente en el primer paso (al entrar en `/register`)."""
        self.register_step = 1
        self._set_field_errors({})
        self.error_message = ""

    @rx.event
    def clear_messages(self) -> None:
        """Limpia los avisos al entrar en una pantalla (evita arrastrar errores)."""
        self.error_message = ""
        self.info_message = ""
        self._set_field_errors({})

    def _advance_step(self) -> None:
        """Comprueba el paso actual y pasa al siguiente si está completo."""
        errors = self._step_errors(self.register_step)
        if errors:
            self._set_field_errors(errors)
            return
        self._set_field_errors({})
        if self.register_step < REGISTER_STEPS:
            self.register_step += 1

    def _step_errors(self, step: int) -> dict[str, str]:
        """Errores de los campos del paso indicado; vacío si el paso está completo."""
        errors: dict[str, str] = {}
        if step == 1:
            message = name_error(self.display_name)
            if message:
                errors["display_name"] = message
        elif step == 2:
            if not _EMAIL_RE.fullmatch(normalized_email(self.email)):
                errors["email"] = "Escribe un correo válido."
            if not _ALIAS_RE.fullmatch(normalized_alias(self.alias)):
                errors["alias"] = (
                    "El alias debe tener 3–20 caracteres: letra inicial y luego letras, "
                    "números o _."
                )
        elif step == 3:
            if not password_is_strong(self.password):
                errors["password"] = (
                    "La contraseña necesita 8 caracteres, una mayúscula, una minúscula "
                    "y un símbolo."
                )
            if not self.password_confirm or self.password_confirm != self.password:
                errors["password_confirm"] = "Las contraseñas no coinciden."
        elif step == 4:
            errors.update(self._birth_date_errors())
            if self.gender not in GENDER_OPTIONS:
                errors["gender"] = "Selecciona tu género."
        return errors

    def _birth_date_errors(self) -> dict[str, str]:
        """Errores de la fecha de nacimiento (vacío si la fecha es válida)."""
        if not self.birth_date.strip():
            return {"birth_date": "Escribe tu fecha para continuar."}
        try:
            parsed = parse_birth_date(self.birth_date)
        except ValueError:
            return {"birth_date": _BIRTH_ERROR}
        age = calculate_age(parsed)
        if not _BIRTH_MIN_AGE <= age <= _BIRTH_MAX_AGE:
            return {"birth_date": _BIRTH_ERROR}
        return {}

    # ------------------------------------------------------------------
    # Eventos de las pantallas (on_click / on_submit / on_load).
    # ------------------------------------------------------------------

    @rx.event
    def handle_register_step(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Envía del formulario del asistente: avanza de paso o cierra el alta."""
        if self.register_step < REGISTER_STEPS:
            self._advance_step()
            return []
        return self._register_event()

    @rx.event
    def handle_register(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Valida en cliente y envía el alta vía fetch; termina en «verificación pendiente»."""
        return self._register_event()

    def _register_event(self) -> rx.event.EventSpec:
        """Valida los datos del alta y devuelve el evento que la envía."""
        self._clear_form_errors()
        today = date.today()
        parsed_birth_date: date | None = None
        if self.birth_date.strip():
            try:
                parsed_birth_date = parse_birth_date(self.birth_date)
            except ValueError:
                parsed_birth_date = None
        errors = validate_register(
            self.email,
            self.password,
            self.password_confirm,
            self.alias,
            self.display_name,
            parsed_birth_date,
            self.gender,
            today,
        )
        if errors:
            self._set_field_errors(errors)
            return []
        payload = {
            "email": normalized_email(self.email),
            "password": self.password,
            "alias": normalized_alias(self.alias),
            "display_name": self.display_name.strip(),
            "birth_date": (parsed_birth_date or today).isoformat(),
            "gender": self.gender,
            "interest_ids": list(self.selected_interest_ids),
        }
        # El alta no inicia sesión (Q15); no se conserva la contraseña.
        self.registered_email = payload["email"]
        self.is_loading = True
        self._clear_secrets()
        return rx.call_script(
            _fetch_script("/api/auth/register", payload),
            callback=AuthState.handle_register_result,
        )

    def handle_register_result(self, result: Any) -> rx.event.EventSpec:
        """Recibe la respuesta de registro; `201` lleva a «verificación pendiente»."""
        self.is_loading = False
        status, body = self._parse_result(result)
        if status != 201:
            self.error_message = self._error_text(body, status)
            # Si el fallo es de un campo, vuelve al paso donde está ese campo.
            step = _ERROR_STEP.get(self._error_code(body, status))
            if step is not None:
                self.register_step = step
            return []
        self.info_message = ""
        return rx.redirect("/verify-pending")

    @rx.event
    def handle_login(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Inicia sesión vía `fetch` (la respuesta HTTP fija las cookies HttpOnly)."""
        self._clear_form_errors()
        if not self.email.strip() or not self.password:
            self.error_message = "Escribe tu correo y tu contraseña."
            return []
        payload = {
            "email": normalized_email(self.email),
            "password": self.password,
        }
        self.is_loading = True
        self._clear_secrets()
        return rx.call_script(
            _fetch_script("/api/auth/login", payload),
            callback=AuthState.handle_login_result,
        )

    def handle_login_result(self, result: Any) -> rx.event.EventSpec:
        """Recibe la respuesta de login; `200` lleva al inicio con la cookie puesta."""
        self.is_loading = False
        status, body = self._parse_result(result)
        if status != 200:
            self.error_message = self._error_text(body, status)
            return []
        # Recarga completa: la guarda de `/` solo ve la cookie en los headers
        # de una petición HTTP nueva (el WebSocket nació antes del login).
        return rx.call_script("window.location.assign('/')")

    @rx.event
    def handle_resend(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Reenvía el correo de confirmación desde «verificación pendiente»."""
        self._clear_form_errors()
        email = normalized_email(self.email) or self.registered_email
        if not email:
            self.error_message = "Escribe tu correo para reenviar la confirmación."
            return []
        self.is_loading = True
        return rx.call_script(
            _fetch_script("/api/auth/resend-verification", {"email": email}),
            callback=AuthState.handle_resend_result,
        )

    def handle_resend_result(self, result: Any) -> list[rx.event.EventSpec]:
        """`202` siempre: el mensaje nunca revela si el correo existe."""
        self.is_loading = False
        status, body = self._parse_result(result)
        if status != 202:
            self.error_message = self._error_text(body, status)
            return []
        self.info_message = "Si el correo está registrado, te enviamos otro enlace."
        return []

    @rx.event
    def handle_forgot(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Pide el enlace de recuperación; la respuesta nunca revela si existe."""
        self._clear_form_errors()
        email = normalized_email(self.email)
        if not _EMAIL_RE.fullmatch(email):
            self.error_email = "Escribe un correo válido."
            return []
        self.is_loading = True
        self._clear_secrets()
        return rx.call_script(
            _fetch_script("/api/auth/forgot-password", {"email": email}),
            callback=AuthState.handle_forgot_result,
        )

    def handle_forgot_result(self, result: Any) -> list[rx.event.EventSpec]:
        """`202` siempre: mensaje neutro aunque el correo no exista."""
        self.is_loading = False
        status, body = self._parse_result(result)
        if status != 202:
            self.error_message = self._error_text(body, status)
            return []
        self.info_message = (
            "Si el correo está registrado, te enviamos un enlace para restablecer la contraseña."
        )
        return []

    @rx.event
    def handle_reset(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Guarda la nueva contraseña con el token del fragmento («/reset-password#token»)."""
        self._clear_form_errors()
        token = self.router.url.fragment.strip()
        if not token:
            self.error_message = _ERROR_TEXTS["unauthorized"]
            return []
        errors: dict[str, str] = {}
        if not password_is_strong(self.password):
            errors["password"] = (
                "La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un símbolo."
            )
        if self.password_confirm != self.password or not self.password_confirm:
            errors["password_confirm"] = "Las contraseñas no coinciden."
        if errors:
            self._set_field_errors(errors)
            return []
        password = self.password
        self.is_loading = True
        self._clear_secrets()
        return rx.call_script(
            _fetch_script("/api/auth/reset-password", {"token": token, "password": password}),
            callback=AuthState.handle_reset_result,
        )

    def handle_reset_result(self, result: Any) -> rx.event.EventSpec:
        """`204` successful: la nueva contraseña queda activa; vuelve a login."""
        self.is_loading = False
        status, body = self._parse_result(result)
        if status != 204:
            self.error_message = self._error_text(body, status)
            return []
        self.info_message = "La contraseña se cambió. Inicia sesión con la nueva."
        return rx.redirect("/login")

    @rx.event
    def handle_confirm(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Intercambia el token del enlace de confirmación y lleva a /login.

        Lee `token_hash`, `code` o los tokens del fragmento del enlace, según
        la plantilla de correo configurada en Supabase.
        """
        self._clear_form_errors()
        self.is_loading = True
        return rx.call_script(
            _CONFIRM_TEMPLATE.replace("@API_BASE@", _API_BASE).replace(
                "@CONFIRM_PATH@", "/api/auth/confirm"
            ),
            callback=AuthState.handle_confirm_result,
        )

    def handle_confirm_result(self, result: Any) -> rx.event.EventSpec:
        """`204` successful: el correo queda confirmado; deja iniciar sesión."""
        self.is_loading = False
        status, body = self._parse_result(result)
        if status != 204:
            self.error_message = self._error_text(body, status)
            return []
        self.info_message = "Correo confirmado. ¡Ya puedes iniciar sesión!"
        return rx.redirect("/login")

    # ------------------------------------------------------------------
    # Comunes
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_result(result: Any) -> tuple[int, dict[str, object]]:
        """Convertir el resultado de `call_script` a (estado_http, cuerpo).

        Devuelve `0` (sin respuesta del servidor) cuando el puente entrega algo
        inesperado, p. ej. un `fetch` que falló o un string no JSON.
        """
        if isinstance(result, str):
            try:
                decoded = json.loads(result)
            except ValueError:
                return 0, {}
        elif isinstance(result, dict):
            decoded = result
        else:
            return 0, {}
        if not isinstance(decoded, dict):
            return 0, {}
        return int(decoded.get("status") or 0), decoded.get("body") or {}

    @classmethod
    def _error_code(cls, body: dict[str, object], status: int) -> str:
        """Código de error del cuerpo de la respuesta (o el del estado HTTP)."""
        error = body.get("error") or {}
        if not isinstance(error, dict):
            error = {}
        code = str(error.get("code") or body.get("error_code") or "")
        if not code:
            code = _ERROR_CODES_BY_STATUS.get(status, "unauthorized")
        return code

    @classmethod
    def _error_text(cls, body: dict[str, object], status: int) -> str:
        """Traduce el código de error del cuerpo al mensaje en español acordado."""
        if status == 0:
            return _NETWORK_ERROR
        code = cls._error_code(body, status)
        return _ERROR_TEXTS.get(code) or _GENERIC_ERRORS.get(status, _UNEXPECTED_ERROR)

    def _clear_form_errors(self) -> None:
        """Resetea los mensajes antes de cada intento."""
        self.error_message = ""
        self.info_message = ""
        self._set_field_errors({})

    def _set_field_errors(self, errors: dict[str, str]) -> None:
        """Vuelca los errores por campo en las vars sueltas que ve el cliente."""
        self.error_display_name = errors.get("display_name", "")
        self.error_email = errors.get("email", "")
        self.error_alias = errors.get("alias", "")
        self.error_password = errors.get("password", "")
        self.error_password_confirm = errors.get("password_confirm", "")
        self.error_birth_date = errors.get("birth_date", "")
        self.error_gender = errors.get("gender", "")

    def _clear_field_error(self, field: str) -> None:
        """Quita el mensaje de error de un campo cuando el usuario lo corrige."""
        if field == "display_name":
            self.error_display_name = ""
        elif field == "email":
            self.error_email = ""
        elif field == "alias":
            self.error_alias = ""
        elif field == "password":
            self.error_password = ""
        elif field == "password_confirm":
            self.error_password_confirm = ""
        elif field == "birth_date":
            self.error_birth_date = ""
        elif field == "gender":
            self.error_gender = ""

    def _clear_secrets(self) -> None:
        """Limpia los campos con credenciales tras cada envío."""
        self.password = ""
        self.password_confirm = ""


_ERROR_CODES_BY_STATUS = {
    401: "invalid_credentials",
    403: "email_not_verified",
    409: "email_already_registered",
    422: "validation_error",
    429: "rate_limited",
}
