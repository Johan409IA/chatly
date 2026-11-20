"""Configuración central de Chatly.

Todas las variables se leen de las variables de entorno o del archivo
`.env` (ver `.env.example`). La instancia se obtiene con `get_settings()`,
que devuelve siempre el mismo objeto cacheado.
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Variables de configuración de la aplicación."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str
    app_database_url: str | None = None
    test_database_url: str | None = None
    supabase_url: str
    supabase_publishable_key: str
    supabase_jwks_url: str
    supabase_avatars_bucket: str = "avatars"
    jwt_leeway_seconds: int = 30

    # Frontend y API viven en puertos distintos en desarrollo. El navegador
    # necesita la URL absoluta del API y CORS con credenciales.
    frontend_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 30
    db_pool_recycle: int = 1800

    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        """Orígenes permitidos para el navegador (lista separada por comas)."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("database_url", "app_database_url", "test_database_url")
    @classmethod
    def _check_driver(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("postgresql+psycopg://"):
            raise ValueError("database_url debe usar el driver postgresql+psycopg")
        return value

    @model_validator(mode="after")
    def _apply_platform_url(self) -> "Settings":
        """Usa la URL pública que Render inyecta en `RENDER_EXTERNAL_URL`.

        El dominio real del servicio no se conoce hasta crearlo (Render añade
        un sufijo), así que se toma de la plataforma: `frontend_url` construye
        el enlace de confirmación del registro y `cors_origins` habilita al
        navegador. El API se sirve en el mismo origen (Caddy hace proxy de
        `/api/*`), por eso `api_public_url` queda vacío.
        """
        external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        if external_url:
            self.frontend_url = external_url
            self.api_public_url = ""
            self.cors_origins = external_url
        return self


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración cacheada (una sola instancia por proceso)."""
    return Settings()  # type: ignore[call-arg]
