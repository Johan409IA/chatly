"""Pruebas del logging JSON y del filtro de redacción (`core/logging.py`)."""

import io
import json
import logging

from Chatly.backend.core.logging import (
    JsonFormatter,
    RedactionFilter,
    _mask_email,
    configure_logging,
    get_logger,
)


def _record(mensaje: str, level: int = logging.INFO, **extra: object) -> logging.LogRecord:
    """Crea un LogRecord como los que llegan a los handlers."""
    record = logging.LogRecord(
        name="chatly.prueba",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=mensaje,
        args=(),
        exc_info=None,
    )
    for campo, valor in extra.items():
        setattr(record, campo, valor)
    return record


def test_json_formatter_produce_json_valido() -> None:
    """El record serializado es JSON con los campos base y los extra."""
    formateador = JsonFormatter()
    record = _record(
        "Mensaje de prueba",
        request_id="req-1",
        actor_id="a-1",
        action="crear",
        entity="mensaje",
        duration_ms=12,
    )

    datos = json.loads(formateador.format(record))

    assert set(datos) == {
        "timestamp",
        "level",
        "logger",
        "message",
        "request_id",
        "actor_id",
        "action",
        "entity",
        "duration_ms",
    }
    assert datos["level"] == "INFO"
    assert datos["logger"] == "chatly.prueba"
    assert datos["message"] == "Mensaje de prueba"
    assert datos["duration_ms"] == 12


def test_mask_email_deja_dominio() -> None:
    """El correo enmascarado conserva dominio, oculta el usuario."""
    assert _mask_email("envia a ana.torres@escuela.edu hoy") == "envia a a***@escuela.edu hoy"


def test_redaction_filter_oculta_secretos_del_mensaje() -> None:
    """El filtro enmascara asignaciones a claves sensibles y correos."""
    filtro = RedactionFilter()
    record = _record(
        "authorization: Bearer abc123def456 token=xyz789 password supersecreta correos ana@mail.com"
    )

    filtro.filter(record)
    texto = record.getMessage()

    assert "abc123def456" not in texto
    assert "xyz789" not in texto
    assert "supersecreta" not in texto
    assert "ana@mail.com" not in texto
    assert "***" in texto
    assert "authorization" in texto  # las claves se mencionan; los valores no
    assert "password" in texto.lower()


def test_redaction_filter_oculta_secretos_de_extras() -> None:
    """Un extra con claves sensibles sale enmascarado, con la clave intacta."""
    filtro = RedactionFilter()
    record = _record(
        "Resumen de petición",
        encabezados={"authorization": "Bearer abc", "content-type": "application/json"},
        apikey="llave-super-secreta",
        correo="usuario@correo.com",
    )

    filtro.filter(record)
    datos_extras = {k: getattr(record, k) for k in ("encabezados", "apikey", "correo")}

    assert datos_extras["encabezados"]["authorization"] == "***"
    assert datos_extras["encabezados"]["content-type"] == "application/json"
    assert datos_extras["apikey"] == "***"
    assert datos_extras["correo"] == "u***@correo.com"


def test_configurado_pipe_output_json_sin_secretos() -> None:
    """Configurando logging real vía stdout: JSON una línea, sin secretos."""
    salida = io.StringIO()
    formateador = JsonFormatter()
    handler = logging.StreamHandler(salida)
    handler.setFormatter(formateador)
    handler.addFilter(RedactionFilter())

    logger = get_logger("chatly.prueba.salida")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info(
            "Petición autorizada por %s de %s",
            "Bearer tokeninvalido123",
            "pepito@correo.com",
            extra={"action": "prueba"},
        )
    finally:
        logger.removeHandler(handler)

    lineas = [linea for linea in salida.getvalue().splitlines() if linea]
    datos = json.loads(lineas[-1])
    assert datos["action"] == "prueba"
    assert "tokeninvalido123" not in json.dumps(datos)
    assert "pepito@correo.com" not in json.dumps(datos)


def test_configure_logging_ajusta_sqlalchemy() -> None:
    """`sqlalchemy.engine` queda en WARNING y el root en el nivel indicado."""
    raiz = logging.getLogger()
    nivel_previo = raiz.level if raiz.level != logging.NOTSET else logging.WARNING
    handlers_previos = raiz.handlers[:]

    try:
        configure_logging("debug")

        assert raiz.level == logging.DEBUG
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
    finally:
        # Restaura el estado del root logger para no contaminar otras pruebas.
        raiz.setLevel(nivel_previo)
        raiz.handlers[:] = handlers_previos
