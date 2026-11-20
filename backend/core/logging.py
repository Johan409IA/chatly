"""Registro de eventos en JSON, sin datos sensibles.

Logs estructurados por línea (JSON Lines) con los campos base `timestamp`,
`level`, `logger` y `message`, más los campos opcionales `request_id`,
`actor_id`, `action`, `entity` y `duration_ms` cuando se pasan.

El `RedactionFilter` enmascara claves sensibles (authorization, tokens,
contraseñas, cookies, etc.) y correos (deja solo la inicial del usuario,
p. ej. `j***@dominio.com`), de modo que ningún secreto llega al archivo de
log aunque un mensaje lo incluya por descuido.
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Campos estructurados opcionales que marcamos como extra del record.
STRUCTURED_FIELDS: tuple[str, ...] = (
    "request_id",
    "actor_id",
    "action",
    "entity",
    "duration_ms",
)

# Claves cuyo valor nunca debe registrarse sin enmascarar.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "token",
        "access_token",
        "refresh_token",
        "apikey",
        "api_key",
        "cookie",
        "set-cookie",
        "password",
        "service_role",
    }
)

# Correo simple: usuario @ dominio con TLD de dos o más letras.
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Atributos estándar de LogRecord, para distinguir los "extra" al serializar.
_RESERVED_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}

_MASQUE = "***"
# `authorization: Bearer abc123`, `token=X`, `password "secreto"`… en texto libre.
_SENSITIVE_IN_TEXT = re.compile(
    r"("
    + "|".join(re.escape(key) for key in sorted(SENSITIVE_KEYS, key=len, reverse=True))
    + r""")[\s:=]+[^\s,;)"']{3,}""",
    re.IGNORECASE,
)
# `Bearer <token>` en texto libre, aunque no vaya precedido de una clave.
_BEARER_IN_TEXT = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)


def _mask_email(value: str) -> str:
    """Enmascara cada correo: `j***@dominio.com` (deja el dominio completo)."""

    def _replace(match: re.Match[str]) -> str:
        email = match.group(0)
        user, _, domain = email.partition("@")
        return f"{user[:1]}{_MASQUE}@{domain}" if user else email

    return _EMAIL_PATTERN.sub(_replace, value)


def _redact_values(obj: Any) -> Any:
    """Recorre dicts/listas: enmascara el valor de claves sensibles y correos."""
    if isinstance(obj, dict):
        return {
            key: _MASQUE
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS
            else _redact_values(value)
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return type(obj)(_redact_values(item) for item in obj)
    if isinstance(obj, str):
        return _redact_text(obj)
    return obj


def _redact_text(text: str) -> str:
    """Enmascara asignaciones a claves sensibles y correos dentro del texto."""
    # Ojo con el orden: primero los bearer, luego las claves, luego los correos.
    text = _BEARER_IN_TEXT.sub("Bearer=***", text)
    text = _SENSITIVE_IN_TEXT.sub(lambda m: f"{m.group(1)}={_MASQUE}", text)
    return _mask_email(text)


class RedactionFilter(logging.Filter):
    """Enmascara secretos y correos en el mensaje y en los campos extra.

    Debe colgar de todo handler (no de un logger concreto) para que ningún
    registro con datos sensibles pase al log, salga del logger que salga.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Sustituye msg+args por el mensaje ya interpolado y redactado.
        record.msg = _redact_text(record.getMessage())
        record.args = ()

        # Enmascara los extras: el atributo con nombre sensible sale como "***"
        # (p. ej. `apikey=...`), y el resto se redacta por dentro y fuera.
        for attr in list(vars(record)):
            if attr in _RESERVED_ATTRS:
                continue
            if attr.lower() in SENSITIVE_KEYS:
                setattr(record, attr, _MASQUE)
                continue
            value = getattr(record, attr)
            if value is None:
                continue
            setattr(record, attr, _redact_values(value))
        return True


class JsonFormatter(logging.Formatter):
    """Serializa cada record en una línea JSON con el envelope acordado."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        # El resto de extras definidos por el emisor se conservan tal cual.
        for attr in vars(record):
            if attr in _RESERVED_ATTRS or attr in STRUCTURED_FIELDS:
                continue
            value = getattr(record, attr)
            if value is not None:
                payload[attr] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configura el root logger con salida JSON y redacción, de forma idempotente.

    - Reemplaza los handlers previos (llamadas repetidas no duplican líneas).
    - `sqlalchemy.engine` queda en WARNING para no emitir el SQL con parámetros.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]  # idempotente: no acumula handlers
    root.setLevel(level.upper())

    # SQLAlchemy libera el SQL con los parámetros reales vía INFO.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger con el nombre indicado (registra vía root)."""
    return logging.getLogger(name)
