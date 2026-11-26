"""Cliente REST del navegador compartido por los estados con sesión.

Las cookies HttpOnly (`chatly_at`/`chatly_rt`) solo se fijan en respuestas
HTTP reales, así que las llamadas autenticadas se hacen con `fetch` desde el
navegador vía `rx.call_script` — nunca como eventos de Reflex (WebSocket).

El script se evalúa con `eval`, así que debe ser una EXPRESIÓN: va entre
paréntesis y se invoca al final (`(...)()`). NUNCA registrar el script
generado: contiene credenciales cuando hay `payload`.

`request_id` permite descartar respuestas obsoletas (la respuesta de una
conversación ya no seleccionada, por ejemplo).
"""

import json
from typing import Any

from Chatly.backend.core.settings import get_settings

# El frontend (:3000) y el API (:8000) son orígenes distintos en desarrollo;
# `fetch` relativo iría al servidor de Vite. Vacío = mismo origen (producción).
_API_BASE = get_settings().api_public_url.rstrip("/")

_API_JS = (
    "const rawApi = '@API_BASE@';"
    "const apiBase = rawApi"
    "  ? (() => { const u = new URL(rawApi); u.hostname = window.location.hostname;"
    "      return u.origin; })()"
    "  : '';"
)


def fetch_script(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    request_id: str = "",
) -> str:
    """Construye el script `fetch` de una llamada autenticada por cookies."""
    options = [
        f"method: {json.dumps(method)}",
        'headers: {"Content-Type": "application/json"}',
        'credentials: "include"',
    ]
    if payload is not None:
        options.append(f"body: JSON.stringify({json.dumps(payload)})")
    return (
        "(async () => {"
        + _API_JS.replace("@API_BASE@", _API_BASE)
        + f"const requestId = {json.dumps(request_id)};"
        + f"const path = {json.dumps(path)};"
        + "try {"
        + "const response = await fetch(apiBase + path, {"
        + ",".join(options)
        + "});"
        + "const text = await response.text();"
        + "let body = {};"
        + "if (text) { try { body = JSON.parse(text); } catch (error) { body = {}; } }"
        + "return JSON.stringify({status: response.status, body, request_id: requestId});"
        + "} catch (error) {"
        + "return JSON.stringify({status: 0, body: {}, request_id: requestId});"
        + "}"
        + "})()"
    )


def parse_response(result: Any) -> tuple[int, dict[str, Any], str]:
    """Convierte el resultado de `call_script` en (estado_http, cuerpo, request_id).

    Devuelve estado `0` (sin respuesta del servidor) cuando el puente entrega
    algo inesperado, p. ej. un `fetch` que falló o un string no JSON.
    """
    if isinstance(result, str):
        try:
            decoded = json.loads(result)
        except ValueError:
            return 0, {}, ""
    elif isinstance(result, dict):
        decoded = result
    else:
        return 0, {}, ""
    if not isinstance(decoded, dict):
        return 0, {}, ""
    status = decoded.get("status")
    body = decoded.get("body")
    request_id = decoded.get("request_id")
    return (
        status if isinstance(status, int) else 0,
        body if isinstance(body, dict) else {},
        request_id if isinstance(request_id, str) else "",
    )
