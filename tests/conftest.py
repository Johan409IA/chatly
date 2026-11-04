"""Fixtures compartidas de las pruebas de Chatly.

En Windows, Psycopg 3 async falla con el ProactorEventLoop; se fija el
SelectorEventLoopPolicy al importar, antes de crear cualquier bucle.

Las pruebas usan dos conexiones:
- Administrativa (`DATABASE_URL`, rol `postgres`): solo DDL de preparación.
- De aplicación (`TEST_DATABASE_URL`, rol `chatly_app`): las aserciones RLS,
  igual que hará la app en producción.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _check_db() -> None:
    """Comprueba conexión a Supabase y que la migración 0001_infra está aplicada.

    Lanza `pytest.skip` con un mensaje claro si falla algo, para que la suite
    siga verde sin red ni credenciales.
    """
    from sqlalchemy import text

    from Chatly.backend.database.session import get_session_factory

    try:
        async with get_session_factory()() as session:
            await session.execute(text("select 1"))
    except Exception as exc:  # pragma: no cover - depende del entorno
        pytest.skip(f"Sin conexión a Supabase: {type(exc).__name__}: {exc}")

    try:
        async with get_session_factory()() as session:
            result = await session.execute(text("select to_regprocedure('app.current_actor_id()')"))
            if result.scalar() is None:
                pytest.skip("Ejecuta `uv run alembic upgrade head` antes de las pruebas.")
    except Exception as exc:  # pragma: no cover - depende del entorno
        pytest.skip(f"Sin conexión a Supabase: {type(exc).__name__}: {exc}")


@pytest.fixture
async def db_available():
    """Marca la prueba como dependiente de Supabase; salta si no hay conexión."""
    await _check_db()
    return True


async def require_app_role() -> str:
    """Garantiza que las aserciones RLS corren como `chatly_app` sin BYPASSRLS.

    Salta si `TEST_DATABASE_URL` no está configurada (suite verde sin
    credenciales) y falla si la conexión usa otro rol o uno con `BYPASSRLS`.
    """
    from sqlalchemy import text

    from Chatly.backend.core.settings import get_settings
    from Chatly.backend.database.session import get_test_session_factory

    if not get_settings().test_database_url:
        pytest.skip("Configura TEST_DATABASE_URL con el rol chatly_app para las pruebas RLS.")

    async with get_test_session_factory()() as session:
        try:
            fila = (
                await session.execute(
                    text(
                        "select current_user, rolbypassrls "
                        "from pg_roles where rolname = current_user"
                    )
                )
            ).fetchone()
        except Exception as exc:  # pragma: no cover - depende del entorno
            pytest.skip(f"Sin conexión con el rol de aplicación: {type(exc).__name__}: {exc}")

    usuario, bypass = fila
    if usuario != "chatly_app" or bypass:
        pytest.fail(
            f"Las pruebas RLS deben correr como chatly_app sin BYPASSRLS; "
            f"la conexión usa '{usuario}' (rolbypassrls={bypass})."
        )
    return str(usuario)


@asynccontextmanager
async def app_transaction(actor_id: str) -> AsyncIterator[Any]:
    """Transacción en el rol de aplicación con el contexto RLS del actor.

    Espejo de lo que hará `session.actor_transaction` en producción: fija
    `app.current_user_id` local a la transacción y hace commit/rollback.
    """
    from sqlalchemy import text

    from Chatly.backend.database.session import get_test_session_factory

    async with get_test_session_factory()() as session:
        async with session.begin():
            await session.execute(
                text("select set_config('app.current_user_id', :uid, true)"),
                {"uid": actor_id},
            )
            yield session


async def run_admin_sql(statements: str | list[str]) -> None:
    """Ejecuta sentencias administrativas (DDL/setup) y hace commit siempre.

    Cada ejecución abre su propia sesión, lo que permite llamarla antes o
    después de las transacciones bajo prueba sin mezclar contextos.
    """
    from sqlalchemy import text

    from Chatly.backend.database.session import get_session_factory

    if isinstance(statements, str):
        statements = [statements]

    async with get_session_factory()() as session:
        for statement in statements:
            await session.execute(text(statement))
        await session.commit()


async def fetch_admin_scalar(sql: str, params: dict[str, object] | None = None) -> object:
    """Ejecuta una consulta de comprobación y devuelve un único valor."""
    from sqlalchemy import text

    from Chatly.backend.database.session import get_session_factory

    async with get_session_factory()() as session:
        result = await session.execute(text(sql), params or {})
        return result.scalar()
