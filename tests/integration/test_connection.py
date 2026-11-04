"""Pruebas de conexión a Supabase y liberación del pool."""

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db


async def test_select_1(db_available: None) -> None:
    """La conexión responde `select 1` con el valor esperado."""
    from Chatly.backend.database.session import get_session_factory

    async with get_session_factory()() as session:
        result = await session.execute(text("select 1"))

    assert result.scalar() == 1


async def test_pool_queda_libre_tras_cerrar(db_available: None) -> None:
    """Al cerrar la sesión, ninguna conexión del engine sigue ocupada."""
    from Chatly.backend.database.session import get_engine, get_session_factory

    async with get_session_factory()() as session:
        await session.execute(text("select 1"))

    # Al salir del context manager, la sesión cierra y devuelve la conexión.
    assert get_engine().pool.checkedout() == 0


async def test_rol_de_aplicacion_conecta_sin_bypassrls(db_available: None) -> None:
    """La conexión de aserciones usa `chatly_app`, sin `BYPASSRLS`."""
    from tests.conftest import require_app_role

    usuario = await require_app_role()
    assert usuario == "chatly_app"
