"""Estado de sesión y guardas de ruta de Reflex.

Sigue `docs/architecture.md` §4.1 y §5.4:

- El servidor lee la cookie `chatly_at` de `self.router.headers.cookie`
  (solo disponible en el servidor, nunca en el frontend).
- El JWT se verifica con el mismo verificador de la API; el actor sale del
  token, nunca de un valor enviado por el cliente.
- Las páginas protegidas declaran `on_load=[SessionState.guard_page]`.
- La verificación de correo confirmado (`require_verified`) se activará con
  la tabla `profiles` (Iteración 2, tareas de perfil).
"""

import asyncio
from http.cookies import SimpleCookie

import reflex as rx

from Chatly.backend.core.jwt import get_jwt_verifier

ACCESS_TOKEN_COOKIE = "chatly_at"


class SessionState(rx.State):
    """Sesión del usuario autenticado en la interfaz."""

    actor_id: str = ""
    alias: str = ""
    email_verified: bool = False

    @rx.var
    def is_authenticated(self) -> bool:
        return self.actor_id != ""

    def _read_access_token(self) -> str | None:
        """Extrae el token de la cookie `chatly_at` del header Cookie."""
        cookie_header = self.router.headers.cookie
        if not cookie_header:
            return None
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        morsel = cookies.get(ACCESS_TOKEN_COOKIE)
        return morsel.value if morsel else None

    @rx.event
    async def guard_page(self) -> rx.event.EventSpec | list[rx.event.EventSpec]:
        """Guarda de `on_load`: resuelve la sesión o redirige a `/login`."""
        if self.actor_id:
            return []

        token = self._read_access_token()
        if not token:
            return rx.redirect("/login")

        try:
            # En un hilo: la descarga del JWKS es I/O síncrono y bloquearía
            # el event loop cuando la caché de claves expira.
            actor = await asyncio.to_thread(get_jwt_verifier().verify, token)
        except Exception:
            return rx.redirect("/login")

        self.actor_id = str(actor.id)
        return []

    @rx.event
    async def redirect_if_authenticated(self) -> rx.event.EventSpec | list[rx.event.EventSpec]:
        """Guarda de `/login`: un usuario con sesión válida pasa al inicio."""
        if self.actor_id:
            return rx.redirect("/")

        token = self._read_access_token()
        if token:
            try:
                actor = await asyncio.to_thread(get_jwt_verifier().verify, token)
                self.actor_id = str(actor.id)
                return rx.redirect("/")
            except Exception:
                return []

        return []
