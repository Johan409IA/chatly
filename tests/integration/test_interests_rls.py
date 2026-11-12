"""Pruebas de aislamiento RLS del catálogo de intereses y su selección.

Las aserciones corren sobre `TEST_DATABASE_URL` (rol `chatly_app`, sin
`BYPASSRLS`), exactamente como la app en producción. La conexión
administrativa (`DATABASE_URL`) solo prepara y limpia los datos de prueba.

El catálogo se lee sin actor mediante `app.catalogo_intereses()`
(`SECURITY DEFINER`), pero las tablas del catálogo siguen exigiendo actor en
sus políticas: sin actor no se ve ninguna fila (`authorization-matrix` §6.1).
"""

from datetime import date
from uuid import UUID

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

# Actores inventados (no corresponden a usuarios reales de Supabase).
ACTOR_A = "00000000-0000-0000-0000-0000000000a1"
ACTOR_B = "00000000-0000-0000-0000-0000000000b1"


async def _crear_usuario_prueba(usuario_id: str, alias: str) -> None:
    """Crea un usuario de Auth y su perfil (FK `perfiles.id -> auth.users`)."""
    await run_admin_sql(
        [
            "insert into auth.users"
            " (id, aud, role, email, encrypted_password, raw_app_meta_data,"
            "  raw_user_meta_data, created_at, updated_at)"
            f" values ('{usuario_id}', 'authenticated', 'authenticated',"
            f" '{alias}@chatly-prueba.local', 'hash-de-prueba', '{{}}', '{{}}',"
            " now(), now())",
            "insert into public.perfiles"
            " (id, alias, nombre_visible, fecha_nacimiento, genero)"
            f" values ('{usuario_id}', '{alias}', 'Usuario de prueba',"
            " date '2000-01-01', 'masculino')",
        ]
    )


@pytest.fixture
async def entorno_intereses(db_available: None) -> None:
    """Prepara dos usuarios de prueba con su perfil; limpia al final."""
    await require_app_role()
    await _crear_usuario_prueba(ACTOR_A, "prueba_a")
    await _crear_usuario_prueba(ACTOR_B, "prueba_b")
    try:
        yield
    finally:
        await run_admin_sql(
            [
                f"delete from auth.users where id in ('{ACTOR_A}', '{ACTOR_B}')",
            ]
        )


async def _primer_interes_activo() -> str:
    """ID de un interés activo del catálogo."""
    interes_id = await fetch_admin_scalar(
        "select id from public.intereses where activo = true order by nombre limit 1"
    )
    assert interes_id is not None
    return str(interes_id)


async def _dos_intereses_activos() -> tuple[UUID, UUID]:
    """IDs de dos intereses activos del catálogo."""
    filas = await fetch_admin_scalar(
        "select array_agg(id) from (select id from public.intereses"
        " where activo = true order by nombre limit 2) t"
    )
    assert filas is not None
    return UUID(str(filas[0])), UUID(str(filas[1]))


async def test_catalogo_se_lee_sin_actor(entorno_intereses: None) -> None:
    """`app.catalogo_intereses()` es el mecanismo público del catálogo."""
    from Chatly.backend.database.session import get_test_session_factory

    async with get_test_session_factory()() as session:
        total = (
            await session.execute(text("select count(*) from app.catalogo_intereses()"))
        ).scalar()
    assert total and total > 0


async def test_catalogo_directo_sin_actor_no_muestra_filas(entorno_intereses: None) -> None:
    """Las políticas del catálogo siguen exigiendo actor (`authorization-matrix` §6.1)."""
    from Chatly.backend.database.session import get_test_session_factory

    async with get_test_session_factory()() as session:
        total = (await session.execute(text("select count(*) from public.intereses"))).scalar()
        categorias = (
            await session.execute(text("select count(*) from public.categorias_interes"))
        ).scalar()
    assert total == 0
    assert categorias == 0


async def test_catalogo_con_actor_muestra_las_filas(entorno_intereses: None) -> None:
    """Con actor, el catálogo activo es visible para el rol de aplicación."""
    async with app_transaction(ACTOR_A) as session:
        total = (await session.execute(text("select count(*) from public.intereses"))).scalar()
    assert total and total > 0


async def test_insert_propio_de_intereses_permitido(entorno_intereses: None) -> None:
    """El actor puede asociarse sus propios intereses."""
    interes_id = await _primer_interes_activo()

    async with app_transaction(ACTOR_A) as session:
        await session.execute(
            text(
                "insert into public.intereses_usuario (usuario_id, interes_id)"
                " values (:usuario, :interes)"
            ),
            {"usuario": ACTOR_A, "interes": interes_id},
        )

    total = await fetch_admin_scalar(
        "select count(*) from public.intereses_usuario where usuario_id = :usuario",
        {"usuario": ACTOR_A},
    )
    assert total == 1


async def test_insert_de_intereses_ajenos_bloqueado(entorno_intereses: None) -> None:
    """El actor no puede asociar intereses a otro usuario (RLS)."""
    interes_id = await _primer_interes_activo()

    with pytest.raises(ProgrammingError):
        async with app_transaction(ACTOR_A) as session:
            await session.execute(
                text(
                    "insert into public.intereses_usuario (usuario_id, interes_id)"
                    " values (:usuario, :interes)"
                ),
                {"usuario": ACTOR_B, "interes": interes_id},
            )

    total = await fetch_admin_scalar(
        "select count(*) from public.intereses_usuario where usuario_id = :usuario",
        {"usuario": ACTOR_B},
    )
    assert total == 0


async def test_select_solo_muestra_los_intereses_propios(entorno_intereses: None) -> None:
    """Cada actor ve únicamente su propia selección."""
    interes_id = await _primer_interes_activo()

    async with app_transaction(ACTOR_A) as session:
        await session.execute(
            text(
                "insert into public.intereses_usuario (usuario_id, interes_id)"
                " values (:usuario, :interes)"
            ),
            {"usuario": ACTOR_A, "interes": interes_id},
        )

    async with app_transaction(ACTOR_A) as session:
        propias = (
            await session.execute(text("select count(*) from public.intereses_usuario"))
        ).scalar()
    async with app_transaction(ACTOR_B) as session:
        ajenas = (
            await session.execute(text("select count(*) from public.intereses_usuario"))
        ).scalar()

    assert propias == 1
    assert ajenas == 0


async def test_visibilidad_publica_por_defecto_true(entorno_intereses: None) -> None:
    """`perfiles.visibilidad_publica` vale `true` y aparece en la vista pública."""
    visibilidad = await fetch_admin_scalar(
        "select visibilidad_publica from public.perfiles where id = :usuario",
        {"usuario": ACTOR_A},
    )
    assert visibilidad is True

    en_vista = await fetch_admin_scalar(
        "select visibilidad_publica from app.perfiles_publicos where id = :usuario",
        {"usuario": ACTOR_A},
    )
    assert en_vista is True


# ------------------------------------------------ persistencia del registro


async def test_alta_con_intereses_persiste_las_filas(entorno_intereses: None) -> None:
    """`create_profile` inserta perfil, contacto y selección en una sola transacción."""
    from Chatly.backend.repositories.profile_repository import get_profile_repository

    usuario_id = "00000000-0000-0000-0000-0000000000c1"
    await run_admin_sql(
        [
            "insert into auth.users"
            " (id, aud, role, email, encrypted_password, raw_app_meta_data,"
            "  raw_user_meta_data, created_at, updated_at)"
            f" values ('{usuario_id}', 'authenticated', 'authenticated',"
            " 'alta_prueba@chatly-prueba.local', 'hash-de-prueba', '{}', '{}', now(), now())",
        ]
    )
    try:
        interes_a, interes_b = await _dos_intereses_activos()
        await get_profile_repository().create_profile(
            user_id=usuario_id,
            alias="alta_prueba",
            display_name="Alta de prueba",
            birth_date=date(2000, 1, 1),
            gender="masculino",
            email="alta_prueba@chatly-prueba.local",
            interest_ids=[interes_a, interes_b],
        )

        filas = await fetch_admin_scalar(
            "select count(*) from public.intereses_usuario where usuario_id = :usuario",
            {"usuario": usuario_id},
        )
        assert filas == 2
        perfil = await fetch_admin_scalar(
            "select alias from public.perfiles where id = :usuario",
            {"usuario": usuario_id},
        )
        assert perfil == "alta_prueba"
    finally:
        await run_admin_sql([f"delete from auth.users where id = '{usuario_id}'"])


async def test_alta_con_interes_invalido_revierte_todo(entorno_intereses: None) -> None:
    """Si un interés no existe, la transacción se revierte y no queda perfil."""
    from Chatly.backend.core.errors import ValidationError
    from Chatly.backend.repositories.profile_repository import get_profile_repository

    usuario_id = "00000000-0000-0000-0000-0000000000c2"
    await run_admin_sql(
        [
            "insert into auth.users"
            " (id, aud, role, email, encrypted_password, raw_app_meta_data,"
            "  raw_user_meta_data, created_at, updated_at)"
            f" values ('{usuario_id}', 'authenticated', 'authenticated',"
            " 'alta_invalida@chatly-prueba.local', 'hash-de-prueba', '{}', '{}', now(), now())",
        ]
    )
    try:
        interes_a, _ = await _dos_intereses_activos()
        with pytest.raises(ValidationError):
            await get_profile_repository().create_profile(
                user_id=usuario_id,
                alias="alta_invalida",
                display_name="Alta inválida",
                birth_date=date(2000, 1, 1),
                gender="masculino",
                email="alta_invalida@chatly-prueba.local",
                interest_ids=[interes_a, UUID("99999999-9999-4999-8999-999999999999")],
            )

        perfil = await fetch_admin_scalar(
            "select count(*) from public.perfiles where id = :usuario",
            {"usuario": usuario_id},
        )
        filas = await fetch_admin_scalar(
            "select count(*) from public.intereses_usuario where usuario_id = :usuario",
            {"usuario": usuario_id},
        )
        assert perfil == 0
        assert filas == 0
    finally:
        await run_admin_sql([f"delete from auth.users where id = '{usuario_id}'"])
