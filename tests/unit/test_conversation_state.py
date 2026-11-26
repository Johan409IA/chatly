"""Pruebas de regresión del estado de conversaciones.

El frontend de conversaciones se trajo en `7fff538` con una llamada a
`self._parse_response`, un método que nunca existió en la clase: cada
`GET /api/conversations` y `GET /api/me` reventaba en el event handler y
Reflex mostraba el aviso genérico «An error occurred». Los tests de API no
cubren el estado de Reflex, así que esta guarda de fuente evita que vuelva
a colarse una llamada a un método inexistente.
"""

from pathlib import Path

from Chatly.state import conversation_state

_RUTA_ESTADO = Path(conversation_state.__file__)


def test_los_handlers_no_llaman_a_metodos_inexistentes() -> None:
    fuente = _RUTA_ESTADO.read_text(encoding="utf-8")
    assert "self._parse_response" not in fuente, (
        "ConversationState llama a _parse_response, que no existe; "
        "usa la función parse_response de Chatly.state.api_client."
    )


def test_la_funcion_parse_response_esta_importada() -> None:
    fuente = _RUTA_ESTADO.read_text(encoding="utf-8")
    assert "from Chatly.state.api_client import fetch_script, parse_response" in fuente


def test_los_metodos_de_clase_definidos_son_los_usados() -> None:
    """Todo `self._x(` del estado debe estar definido en la clase."""
    import re

    fuente = _RUTA_ESTADO.read_text(encoding="utf-8")
    usados = set(re.findall(r"self\.(_\w+)\(", fuente))
    definidos = set(re.findall(r"def (_\w+)\(", fuente))
    indefinidos = usados - definidos
    assert indefinidos == set(), f"Métodos usados pero no definidos: {indefinidos}"
