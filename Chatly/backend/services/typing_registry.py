"""Registro efímero de «escribiendo…» (puente REST hasta la Iteración 6).

El diseño final (`docs/realtime-events.md` §7) transporta la señal como
Broadcast en `conversation:<uuid>` sin persistirla. Mientras Realtime no
está cableado, la señal vive en la memoria del proceso con un TTL de cinco
segundos (Q77/Q96) y el otro participante la lee por sondeo REST. El
despliegue actual es de una sola instancia, así que el estado por proceso
basta; con réplicas habría que pasar a Realtime.
"""

import time
from functools import lru_cache
from uuid import UUID

# Q96: el indicador desaparece tras cinco segundos sin actividad.
_TYPING_TTL_SECONDS = 5.0


class TypingRegistry:
    """Señales de escritura por conversación, con caducidad automática."""

    def __init__(self, ttl_seconds: float = _TYPING_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        # (conversacion_id, usuario_id) -> instante de expiración.
        self._signals: dict[tuple[UUID, UUID], float] = {}

    def record_typing(
        self, conversation_id: UUID, user_id: UUID, *, is_typing: bool = True
    ) -> None:
        """Registra o retira la señal del usuario en la conversación."""
        key = (conversation_id, user_id)
        if is_typing:
            self._signals[key] = time.monotonic() + self._ttl_seconds
        else:
            self._signals.pop(key, None)

    def typing_members(self, conversation_id: UUID, *, exclude_user_id: UUID) -> list[UUID]:
        """Ids de quienes siguen escribiendo, sin contar al propio actor.

        Las señales caducadas se descartan al vuelo (sin barrido global).
        """
        now = time.monotonic()
        return [
            user_id
            for (conversation, user_id), expires_at in list(self._signals.items())
            if conversation == conversation_id
            and user_id != exclude_user_id
            and expires_at > now
        ]


@lru_cache
def get_typing_registry() -> TypingRegistry:
    """Instancia única del registro por proceso (sustituible en tests)."""
    return TypingRegistry()
