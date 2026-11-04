"""Pruebas unitarias de la configuración central (`backend/core/settings.py`)."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from Chatly.backend.core.settings import Settings

# URL de ejemplo válida para el constructor (no toca el `.env`).
URL_OK = "postgresql+psycopg://usuario:secreto@host:5432/postgres?sslmode=require"


def _settings(**overrides: str) -> Settings:
    """Instancia Settings solo con lo que se pasa (ignora `.env` y variables)."""
    kwargs: dict[str, str] = {
        "database_url": URL_OK,
        "supabase_url": "https://proyecto.supabase.co",
        "supabase_publishable_key": "sb_publishable_prueba",
        "supabase_jwks_url": "https://proyecto.supabase.co/auth/v1/.well-known/jwks.json",
    }
    kwargs.update(overrides)
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_valores_por_defecto() -> None:
    """Los campos de pool y log tienen los valores acordados."""
    settings = _settings()

    assert settings.app_env == "development"
    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 10
    assert settings.db_pool_timeout == 30
    assert settings.db_pool_recycle == 1800
    assert settings.log_level == "INFO"
    assert settings.supabase_avatars_bucket == "avatars"


def test_lee_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las variables preceden a los valores por defecto."""
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "13")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "12.5")
    monkeypatch.setenv("DB_POOL_RECYCLE", "900")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_ENV", "test")

    settings = _settings()

    assert settings.db_pool_size == 7
    assert settings.db_max_overflow == 13
    assert settings.db_pool_timeout == 12.5
    assert settings.db_pool_recycle == 900
    assert settings.log_level == "DEBUG"
    assert settings.app_env == "test"


def test_rechaza_driver_no_psycopg() -> None:
    """El driver del `database_url` debe ser siempre `postgresql+psycopg`."""
    with pytest.raises(PydanticValidationError, match="postgresql\\+psycopg"):
        _settings(database_url="postgresql://usuario:secreto@host:5432/postgres")


def test_acepta_driver_psycopg() -> None:
    """La URL correcta pasa la validación sin cambios."""
    url = "postgresql+psycopg://u:s@h:5432/postgres?sslmode=require"
    assert _settings(database_url=url).database_url == url


def test_get_settings_cacheado() -> None:
    """get_settings devuelve siempre la misma instancia."""
    from Chatly.backend.core.settings import get_settings

    try:
        get_settings.cache_clear()
        primera = get_settings()
        segunda = get_settings()
    except Exception as exc:  # pragma: no cover - sin .env en el entorno
        pytest.skip(f"Sin configuración disponible: {type(exc).__name__}")
        return

    assert primera is segunda
    get_settings.cache_clear()
