"""Pruebas de aislamiento RLS con el rol de aplicación `chatly_app`.

Las aserciones corren sobre `TEST_DATABASE_URL` (rol `chatly_app`, sin
`BYPASSRLS`), exactamente como la app en producción. La conexión
administrativa (`DATABASE_URL`) solo crea y elimina el DDL de prueba.

La política evalúa `app.current_actor_id()` directamente: `chatly_app`
resuelve `auth.uid()` gracias a su membresía en `authenticated` (con
`rolinherit` activado). No se usan roles temporales ni helpers
`SECURITY DEFINER`.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from tests.conftest import (
    app_transaction,
    fetch_admin_scalar,
    require_app_role,
    run_admin_sql,
)

pytestmark = pytest.mark.db

SCHEMA_PRUEBA = "pruebas_rls"
TABLA_PRUEBA = f"{SCHEMA_PRUEBA}.registros"

# Actores inventados (no corresponden a usuarios reales de Supabase).
ACTOR_A = "00000000-0000-0000-0000-00000000000a"
ACTOR_B = "00000000-0000-0000-0000-00000000000b"


@pytest.fixture
async def entorno_rls(db_available: None) -> None:
    """Prepara schema, tabla con RLS y filas de A y B; limpia al final."""
    await require_app_role()
    await run_admin_sql(
        [
            f"drop schema if exists {SCHEMA_PRUEBA} cascade",
            f"create schema {SCHEMA_PRUEBA}",
            f"""
            create table {TABLA_PRUEBA} (
                id uuid primary key default gen_random_uuid(),
                propietario_id uuid not null,
                contenido text not null
            )
            """,
            f"alter table {TABLA_PRUEBA} enable row level security",
            f"""
            create policy rls_pruebas_registros on {TABLA_PRUEBA}
            using (app.current_actor_id() = propietario_id)
            with check (app.current_actor_id() = propietario_id)
            """,
            f"grant usage on schema {SCHEMA_PRUEBA} to chatly_app",
            f"grant select, insert, update on {TABLA_PRUEBA} to chatly_app",
        ]
    )
    # Filas de semilla con la conexión administrativa (BYPASSRLS).
    await run_admin_sql(
        [
            f"insert into {TABLA_PRUEBA} (propietario_id, contenido) "
            f"values ('{ACTOR_A}', 'nota-de-A')",
            f"insert into {TABLA_PRUEBA} (propietario_id, contenido) "
            f"values ('{ACTOR_B}', 'nota-de-B')",
        ]
    )
    try:
        yield
    finally:
        await run_admin_sql(f"drop schema if exists {SCHEMA_PRUEBA} cascade")


async def test_cada_actor_solo_ve_sus_filas(entorno_rls: None) -> None:
    """La petición autenticada simulada consulta únicamente filas permitidas."""
    async with app_transaction(ACTOR_A) as session:
        filas = await session.execute(
            text(f"select contenido from {TABLA_PRUEBA} order by contenido")
        )
        assert list(filas.scalars().all()) == ["nota-de-A"]

    async with app_transaction(ACTOR_B) as session:
        filas = await session.execute(
            text(f"select contenido from {TABLA_PRUEBA} order by contenido")
        )
        assert list(filas.scalars().all()) == ["nota-de-B"]


async def test_transacciones_consecutivas_no_comparten_contexto(entorno_rls: None) -> None:
    """Dos transacciones seguidas con actores distintos sobre la MISMA
    conexión del pool no comparten el contexto de identidad."""
    from Chatly.backend.database.session import get_test_engine

    async with get_test_engine().connect() as conexion:  # una sola conexión física
        # Transacción 1: actor A.
        async with conexion.begin():
            await conexion.execute(
                text("select set_config('app.current_user_id', :uid, true)"),
                {"uid": ACTOR_A},
            )
            filas = await conexion.execute(
                text(f"select contenido from {TABLA_PRUEBA} order by contenido")
            )
            assert list(filas.scalars().all()) == ["nota-de-A"]

        # Transacción 2: actor B sobre la misma conexión, sin filtrar el
        # contexto de A (set_config era local a la transacción cerrada).
        async with conexion.begin():
            await conexion.execute(
                text("select set_config('app.current_user_id', :uid, true)"),
                {"uid": ACTOR_B},
            )
            filas = await conexion.execute(
                text(f"select contenido from {TABLA_PRUEBA} order by contenido")
            )
            assert list(filas.scalars().all()) == ["nota-de-B"]


async def test_contexto_descartado_tras_commit(entorno_rls: None) -> None:
    """Tras el commit, `current_setting('app.current_user_id', true)` es vacío."""
    from Chatly.backend.database.session import get_test_engine

    async with get_test_engine().connect() as conexion:
        async with conexion.begin():
            await conexion.execute(
                text("select set_config('app.current_user_id', :uid, true)"),
                {"uid": ACTOR_A},
            )

        async with conexion.begin():
            valor = await conexion.execute(
                text("select current_setting('app.current_user_id', true)")
            )
            assert valor.scalar() in (None, "")


async def test_contexto_descartado_tras_rollback(entorno_rls: None) -> None:
    """Un rollback también descarta el contexto fijado en la transacción."""
    from Chatly.backend.database.session import get_test_engine

    async with get_test_engine().connect() as conexion:
        transaccion = await conexion.begin()
        await conexion.execute(
            text("select set_config('app.current_user_id', :uid, true)"),
            {"uid": ACTOR_B},
        )
        await transaccion.rollback()

        async with conexion.begin():
            valor = await conexion.execute(
                text("select current_setting('app.current_user_id', true)")
            )
            assert valor.scalar() in (None, "")


async def test_rol_app_sin_bypassrls(entorno_rls: None) -> None:
    """El rol de aplicación no puede saltarse las políticas."""
    bypass = await fetch_admin_scalar(
        "select rolbypassrls from pg_roles where rolname = 'chatly_app'"
    )
    assert bypass is False


async def test_insert_propio_permitido_y_ajeno_bloqueado(entorno_rls: None) -> None:
    """El actor A inserta su fila (`with check`) y no puede insertar para B."""
    async with app_transaction(ACTOR_A) as session:
        await session.execute(
            text(
                f"insert into {TABLA_PRUEBA} (propietario_id, contenido) "
                "values (:uid, 'anadida-por-A')"
            ),
            {"uid": ACTOR_A},
        )

    total_a = await fetch_admin_scalar(
        f"select count(*) from {TABLA_PRUEBA} where propietario_id = :uid",
        {"uid": ACTOR_A},
    )
    assert total_a == 2

    with pytest.raises(ProgrammingError):
        async with app_transaction(ACTOR_A) as session:
            await session.execute(
                text(
                    f"insert into {TABLA_PRUEBA} (propietario_id, contenido) "
                    "values (:uid, 'suplantacion')"
                ),
                {"uid": ACTOR_B},
            )

    total_b = await fetch_admin_scalar(
        f"select count(*) from {TABLA_PRUEBA} where propietario_id = :uid",
        {"uid": ACTOR_B},
    )
    assert total_b == 1
