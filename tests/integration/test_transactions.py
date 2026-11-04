"""Pruebas de commits, rollbacks y liberación de conexiones del pool.

Usa la tabla efímera `pruebas_it.notas`; se crea y elimina en cada prueba,
con teardown garantizado aunque alguna aserción falle.
"""

import pytest
from sqlalchemy import text

from tests.conftest import fetch_admin_scalar, run_admin_sql

pytestmark = pytest.mark.db


@pytest.fixture
async def tabla_notas(db_available: None) -> str:
    """Crea `pruebas_it.notas` y la elimina al final de la prueba."""
    await run_admin_sql(
        [
            "create schema if not exists pruebas_it",
            "drop table if exists pruebas_it.notas",
            """
            create table pruebas_it.notas (
                id uuid primary key default gen_random_uuid(),
                texto text not null
            )
            """,
        ]
    )
    try:
        yield "pruebas_it.notas"
    finally:
        await run_admin_sql("drop schema if exists pruebas_it cascade")


async def test_commit_persiste(tabla_notas: str) -> None:
    """Una fila insertada con commit sigue visible en otra sesión."""
    from Chatly.backend.database.session import get_engine, get_session_factory

    async with get_session_factory()() as session:
        async with session.begin():
            await session.execute(text(f"insert into {tabla_notas} (texto) values ('persistente')"))

    total = await fetch_admin_scalar(f"select count(*) from {tabla_notas}")
    assert total == 1
    assert get_engine().pool.checkedout() == 0


async def test_rollback_manual_descarta(tabla_notas: str) -> None:
    """Rollback descarta la fila y la conexión vuelve al pool."""
    from Chatly.backend.database.session import get_engine, get_session_factory

    async with get_session_factory()() as session:
        await session.execute(text(f"insert into {tabla_notas} (texto) values ('temporal')"))
        await session.rollback()

    total = await fetch_admin_scalar(f"select count(*) from {tabla_notas}")
    assert total == 0
    assert get_engine().pool.checkedout() == 0


async def test_rollback_por_excepcion_descarta(tabla_notas: str) -> None:
    """Excepción dentro de `session.begin()` hace rollback de la fila."""
    from Chatly.backend.database.session import get_engine, get_session_factory

    with pytest.raises(RuntimeError, match="abortar"):
        async with get_session_factory()() as session:
            async with session.begin():
                await session.execute(text(f"insert into {tabla_notas} (texto) values ('fallida')"))
                raise RuntimeError("abortar")

    total = await fetch_admin_scalar(f"select count(*) from {tabla_notas}")
    assert total == 0
    assert get_engine().pool.checkedout() == 0
