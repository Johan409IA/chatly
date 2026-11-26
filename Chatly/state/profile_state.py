"""Estado de la pantalla de perfil propio (`/profile`).

Consume `GET/PATCH /api/me` y `PUT /api/me/interests` con `fetch` desde el
navegador (cookies HttpOnly), igual que el resto de estados con sesión. El
catálogo de intereses se lee en el servidor porque el endpoint es público
y no necesita cookies (misma regla que el registro).

Reglas de la Iteración 2 que cubre:
- Edición de intereses con límite de 10 y contador `N/10` (Q117, Q124).
- Cambio de alias con cooldown de 30 días (Q107): si `can_change_alias` es
  `False` el campo se deshabilita y se explica el motivo.
- `is_public` activado por defecto e independiente de los grupos (Q116,
  Q139, Q165): el toggle solo envía `{"is_public": ...}`.
"""

from datetime import date
from typing import Any

import reflex as rx

from Chatly.backend.repositories.interest_repository import get_interest_repository
from Chatly.backend.schemas.auth import (
    _AGE_MESSAGE,
    _ALIAS_MESSAGE,
    _ALIAS_RE,
    _MAX_AGE,
    _MIN_AGE,
)
from Chatly.state.api_client import fetch_script, parse_response
from Chatly.state.auth_state import (
    MAX_INTERESTS,
    InterestCategory,
    InterestItem,
    name_error,
    normalized_alias,
)

_GENDER_OPTIONS = ("femenino", "masculino")

_ERROR_TEXTS = {
    "alias_taken": "Ese alias ya está en uso. Elige otro.",
    "interest_limit_exceeded": f"Puedes elegir hasta {MAX_INTERESTS} intereses.",
    "validation_error": "Revisa los datos del formulario.",
    "rate_limited": "Demasiados intentos. Espera unos minutos y prueba de nuevo.",
}

_GENERIC_ERROR = "No se pudo completar la solicitud. Inténtalo otra vez."
_SESSION_EXPIRED = "Tu sesión ha caducado. Inicia sesión de nuevo."
_NETWORK_ERROR = "No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo otra vez."


class ProfileState(rx.State):
    """Datos y eventos de la pantalla de perfil."""

    # Datos vigentes según el servidor (GET /api/me).
    email: str = ""
    email_verified: bool = False
    age: int = 0
    can_change_alias: bool = True
    is_public: bool = True

    # Campos editables del formulario.
    edit_display_name: str = ""
    edit_alias: str = ""
    edit_birth_date: str = ""  # ISO «yyyy-mm-dd» tal como llega del input date.
    edit_gender: str = ""

    # Catálogo y selección de intereses (el PUT reemplaza la selección completa).
    interest_catalog: list[InterestCategory] = []
    selected_interest_ids: list[str] = []

    # Estados de UI.
    is_loading: bool = False
    is_saving_profile: bool = False
    is_saving_interests: bool = False
    is_saving_visibility: bool = False
    profile_error: str = ""
    profile_message: str = ""
    interest_message: str = ""
    error_display_name: str = ""
    error_alias: str = ""
    error_birth_date: str = ""

    @rx.var
    def interests_count_text(self) -> str:
        """Contador `N/10` de la selección actual."""
        return f"{len(self.selected_interest_ids)}/{MAX_INTERESTS}"

    @rx.var
    def email_verified_text(self) -> str:
        return "Correo verificado" if self.email_verified else "Correo sin confirmar"

    @rx.var
    def alias_hint(self) -> str:
        if self.can_change_alias:
            return "3–20 caracteres: letra inicial y luego letras, números o _."
        return "Puedes cambiar tu alias una vez cada 30 días."

    # ------------------------------------------------------------------
    # Setters de los inputs (Reflex 0.10 no genera `set_<campo>` solo).
    # ------------------------------------------------------------------

    @rx.event
    def set_edit_display_name(self, value: str) -> None:
        self.edit_display_name = value
        self.error_display_name = ""
        self.profile_message = ""

    @rx.event
    def set_edit_alias(self, value: str) -> None:
        self.edit_alias = value
        self.error_alias = ""
        self.profile_message = ""

    @rx.event
    def set_edit_birth_date(self, value: str) -> None:
        self.edit_birth_date = value
        self.error_birth_date = ""
        self.profile_message = ""

    @rx.event
    def set_edit_gender(self, value: str) -> None:
        self.edit_gender = value
        self.profile_message = ""

    # ------------------------------------------------------------------
    # Carga inicial.
    # ------------------------------------------------------------------

    @rx.event
    async def load_catalog(self) -> None:
        """Carga el catálogo público de intereses (una sola vez)."""
        if self.interest_catalog:
            return
        try:
            catalog = await get_interest_repository().list_catalog()
        except Exception:  # pragma: no cover - depende del entorno
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
    def load_profile(self) -> rx.event.EventSpec:
        """Carga el perfil propio desde `GET /api/me`."""
        self.is_loading = True
        self.profile_error = ""
        self.profile_message = ""
        return rx.call_script(
            fetch_script("/api/me"),
            callback=ProfileState.handle_profile_result,
        )

    @rx.event
    def handle_profile_result(self, result: Any) -> rx.event.EventSpec | list:
        status, body, _ = parse_response(result)
        if status == 401:
            return rx.redirect("/login")
        if status != 200:
            self.is_loading = False
            self.profile_error = _profile_error(body, status)
            return []
        self._apply_profile(body)
        return []

    def _apply_profile(self, body: dict[str, Any]) -> None:
        """Vuelca `ProfileMeDTO` en las vars de la pantalla."""
        self.email = str(body.get("email") or "")
        self.email_verified = bool(body.get("email_verified"))
        self.edit_display_name = str(body.get("display_name") or "")
        self.edit_alias = str(body.get("alias") or "")
        self.edit_birth_date = str(body.get("birth_date") or "")[:10]
        self.edit_gender = str(body.get("gender") or "")
        self.age = body.get("age") if isinstance(body.get("age"), int) else 0
        self.can_change_alias = bool(body.get("can_change_alias"))
        self.is_public = bool(body.get("is_public"))
        interests = body.get("interests")
        self.selected_interest_ids = (
            [str(item["id"]) for item in interests if isinstance(item, dict) and item.get("id")]
            if isinstance(interests, list)
            else []
        )
        self.interest_message = ""
        self.is_loading = False

    # ------------------------------------------------------------------
    # Edición de intereses.
    # ------------------------------------------------------------------

    @rx.event
    def toggle_interest(self, interest_id: str) -> None:
        """Añade o quita un interés; el máximo es 10 (Q124)."""
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

    @rx.event
    def save_interests(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Reemplaza la selección completa con `PUT /api/me/interests` (§16.2)."""
        self.interest_message = ""
        self.is_saving_interests = True
        return rx.call_script(
            fetch_script(
                "/api/me/interests",
                method="PUT",
                payload={"interest_ids": list(self.selected_interest_ids)},
            ),
            callback=ProfileState.handle_interests_result,
        )

    @rx.event
    def handle_interests_result(self, result: Any) -> rx.event.EventSpec | list:
        status, body, _ = parse_response(result)
        self.is_saving_interests = False
        if status == 401:
            return rx.redirect("/login")
        if status != 200:
            self.interest_message = _profile_error(body, status)
            return []
        self._apply_profile(body)
        self.interest_message = "Intereses actualizados."
        return []

    # ------------------------------------------------------------------
    # Edición de datos del perfil.
    # ------------------------------------------------------------------

    @rx.event
    def save_profile(self, _form_data: dict | None = None) -> rx.event.EventSpec:
        """Valida en cliente y envía `PATCH /api/me`; responde con el perfil vigente."""
        self.profile_error = ""
        self.profile_message = ""
        errors: dict[str, str] = {}
        message = name_error(self.edit_display_name)
        if message:
            errors["display_name"] = message
        if not _ALIAS_RE.fullmatch(normalized_alias(self.edit_alias)):
            errors["alias"] = _ALIAS_MESSAGE
        errors.update(self._birth_date_errors())
        if errors:
            self.error_display_name = errors.get("display_name", "")
            self.error_alias = errors.get("alias", "")
            self.error_birth_date = errors.get("birth_date", "")
            return []
        payload = {
            "display_name": self.edit_display_name.strip(),
            "alias": normalized_alias(self.edit_alias),
            "birth_date": self.edit_birth_date.strip(),
            "gender": self.edit_gender,
        }
        self.is_saving_profile = True
        return rx.call_script(
            fetch_script("/api/me", method="PATCH", payload=payload),
            callback=ProfileState.handle_save_profile_result,
        )

    @rx.event
    def handle_save_profile_result(self, result: Any) -> rx.event.EventSpec | list:
        status, body, _ = parse_response(result)
        self.is_saving_profile = False
        if status == 401:
            return rx.redirect("/login")
        if status != 200:
            code = _error_code(body, status)
            if code == "alias_taken":
                self.error_alias = _ERROR_TEXTS["alias_taken"]
            else:
                self.profile_error = _profile_error(body, status)
            return []
        self._apply_profile(body)
        self.profile_message = "Perfil actualizado."
        return []

    def _birth_date_errors(self) -> dict[str, str]:
        """Errores de la fecha de nacimiento (vacío si la fecha es válida)."""
        if not self.edit_birth_date.strip():
            return {"birth_date": "Escribe tu fecha para continuar."}
        try:
            parsed = date.fromisoformat(self.edit_birth_date.strip())
        except ValueError:
            return {"birth_date": _AGE_MESSAGE}
        today = date.today()
        age = today.year - parsed.year
        if (today.month, today.day) < (parsed.month, parsed.day):
            age -= 1
        if not _MIN_AGE <= age <= _MAX_AGE:
            return {"birth_date": _AGE_MESSAGE}
        return {}

    # ------------------------------------------------------------------
    # Visibilidad pública.
    # ------------------------------------------------------------------

    @rx.event
    def set_visibility(self, checked: bool) -> rx.event.EventSpec:
        """Activa o desactiva `is_public` con `PATCH /api/me` (§5.2)."""
        self.is_public = checked
        self.profile_error = ""
        self.is_saving_visibility = True
        return rx.call_script(
            fetch_script("/api/me", method="PATCH", payload={"is_public": checked}),
            callback=ProfileState.handle_visibility_result,
        )

    @rx.event
    def handle_visibility_result(self, result: Any) -> rx.event.EventSpec | list:
        status, body, _ = parse_response(result)
        self.is_saving_visibility = False
        if status == 401:
            return rx.redirect("/login")
        if status != 200:
            self.profile_error = _profile_error(body, status)
            # El conmutador queda como estaba: se recupera la verdad del servidor.
            return self.load_profile()
        self.is_public = bool(body.get("is_public"))
        return []


def _error_code(body: dict[str, Any], status: int) -> str:
    """Código de error del cuerpo de la respuesta (o el del estado HTTP)."""
    error = body.get("error") or {}
    if not isinstance(error, dict):
        error = {}
    code = str(error.get("code") or "")
    if not code:
        code = {401: "unauthorized", 404: "not_found", 422: "validation_error"}.get(status, "")
    return code


def _profile_error(body: dict[str, Any], status: int) -> str:
    """Mensaje en español para la pantalla según la respuesta del servidor."""
    if status == 0:
        return _NETWORK_ERROR
    if status == 401:
        return _SESSION_EXPIRED
    if status == 404:
        return "Tu perfil todavía no existe. Vuelve a iniciar sesión."
    error = body.get("error") or {}
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return str(error["message"])
    code = _error_code(body, status)
    return _ERROR_TEXTS.get(code) or _GENERIC_ERROR
