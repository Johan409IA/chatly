"""Motor asíncrono, sesiones y contexto de identidad RLS.

El engine se crea de forma perezosa para que importar este módulo no exija
tener las variables de entorno cargadas (por ejemplo, en pruebas unitarias).
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from Chatly.backend.core.settings import Settings, get_settings


def _pool_kwargs(settings: Settings) -> dict[str, object]:
    """Parámetros de pool compartidos por todos los engines."""
    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        "pool_pre_ping": True,
    }


@lru_cache
def get_engine() -> AsyncEngine:
    """Devuelve el engine asíncrono principal (una instancia por proceso)."""
    settings = get_settings()
    return create_async_engine(settings.database_url, **_pool_kwargs(settings))


@lru_cache
def get_test_engine() -> AsyncEngine:
    """Engine para pruebas con el rol de aplicación (`TEST_DATABASE_URL`).

    Usa la URL del rol sin `BYPASSRLS` (`chatly_app`); si no está configurada,
    reutiliza la URL principal.
    """
    settings = get_settings()
    url = settings.test_database_url or settings.database_url
    return create_async_engine(url, **_pool_kwargs(settings))


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Factoría de sesiones asociada al engine principal."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def get_test_session_factory() -> async_sessionmaker[AsyncSession]:
    """Factoría de sesiones del rol de aplicación para las pruebas."""
    return async_sessionmaker(get_test_engine(), expire_on_commit=False)


async def set_actor_context(session: AsyncSession, actor_id: uuid.UUID) -> None:
    """Fija el actor de la transacción actual para las políticas RLS.

    El tercer argumento `true` de `set_config` hace el ajuste local a la
    transacción: PostgreSQL lo descarta al terminar, de modo que no se filtra
    a la siguiente petición que reutilice la conexión del pool.
    """
    await session.execute(
        text("select set_config('app.current_user_id', :uid, true)"),
        {"uid": str(actor_id)},
    )


@asynccontextmanager
async def actor_transaction(actor_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Abre una transacción con el contexto RLS del actor y la cierra siempre.

    Hace commit si el bloque termina sin error y rollback si lanza una
    excepción. Al salir se devuelve la conexión al pool.
    """
    async with get_session_factory()() as session:
        async with session.begin():
            await set_actor_context(session, actor_id)
            yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI que entrega una sesión y la cierra al final."""
    async with get_session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    """Cierra los engines que llegaron a crearse."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    if get_test_engine.cache_info().currsize:
        await get_test_engine().dispose()
