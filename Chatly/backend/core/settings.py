"""Configuración central de Chatly.

Todas las variables se leen de las variables de entorno o del archivo
`.env` (ver `.env.example`). La instancia se obtiene con `get_settings()`,
que devuelve siempre el mismo objeto cacheado.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de configuración de la aplicación."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str
    test_database_url: str | None = None
    supabase_url: str
    supabase_publishable_key: str
    supabase_jwks_url: str
    supabase_avatars_bucket: str = "avatars"

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 30
    db_pool_recycle: int = 1800

    log_level: str = "INFO"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _check_driver(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("postgresql+psycopg://"):
            raise ValueError("database_url debe usar el driver postgresql+psycopg")
        return value


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada (una sola instancia por proceso)."""
    return Settings()  # type: ignore[call-arg]
