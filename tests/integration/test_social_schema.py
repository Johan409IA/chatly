"""Pruebas de integración del esquema social (migración `0013`).

Corren sobre Supabase real (patrón de `test_rls_context.py`): la conexión
administrativa prepara datos y la de aplicación (`chatly_app`) verifica RLS.
Las filas de prueba se eliminan al terminar; no se tocan las conversaciones
reales de las cuentas existentes.

No se puede probar el trigger de capacidad con 11 usuarios: `perfiles` exige
FK a `auth.users` y solo hay 3 cuentas reales; con 3 integrantes el grupo es
válido. La verificación completa del límite 10 queda para las cuentas demo
(Iteración 9); el trigger instalado sí se comprueba.
"""

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.conftest import (
    app_transaction,
    require_app_role,
)

pytestmark = pytest.mark.db


async def _admin_scalar(sql: str, params: dict | None = None) -> UUID:
    """INSERT con `returning` y commit propio (conftest no commitea)."""
    from Chatly.backend.database.session import get_session_factory

    async with get_session_factory()() as session:
        result = await session.execute(text(sql), params or {})
        await session.commit()
        return UUID(str(result.scalar()))


async def _perfiles_reales() -> list[UUID]:
    """IDs de los perfiles existentes (FK a auth.users: no se pueden inventar)."""
    from Chatly.backend.database.session import get_session_factory

    async with get_session_factory()() as session:
        rows = (
            (
                await session.execute(
                    text(
                        "select id from public.perfiles "
                        "where eliminado_en is null order by creado_en limit 3"
                    )
                )
            )
            .scalars()
            .all()
        )
    return [UUID(str(row)) for row in rows]


@pytest.fixture
async def entorno_social(db_available):
    """Dos grupos y una conversación directa de prueba; limpia al final."""
    perfiles = await _perfiles_reales()
    if len(perfiles) < 3:
        pytest.skip("Se necesitan 3 perfiles reales para las pruebas sociales.")

    a, b, c = perfiles
    conversacion_directa = await _admin_scalar(
        "insert into public.conversaciones (tipo, creado_por, "
        "usuario_directo_menor, usuario_directo_mayor) "
        "values ('direct', :actor, least(:a, :b), greatest(:a, :b)) returning id",
        {"actor": a, "a": a, "b": b},
    )
    grupo_1 = await _admin_scalar(
        "insert into public.conversaciones (tipo, nombre, creado_por, administrador_id) "
        "values ('group', 'Pruebas Sociales 1', :actor, :actor) returning id",
        {"actor": a},
    )
    grupo_2 = await _admin_scalar(
        "insert into public.conversaciones (tipo, nombre, creado_por, administrador_id) "
        "values ('group', 'Pruebas Sociales 2', :actor, :actor) returning id",
        {"actor": a},
    )
    await _admin(
        [
            "insert into public.miembros_conversacion (conversacion_id, usuario_id, rol) "
            f"values ('{grupo_1}', '{a}', 'admin'), ('{grupo_1}', '{b}', 'member')",
            f"insert into public.miembros_conversacion (conversacion_id, usuario_id, rol) "
            f"values ('{grupo_2}', '{a}', 'admin')",
        ]
    )

    try:
        yield {
            "a": a,
            "b": b,
            "c": c,
            "directa": UUID(str(conversacion_directa)),
            "grupo_1": UUID(str(grupo_1)),
            "grupo_2": UUID(str(grupo_2)),
        }
    finally:
        await _admin(
            [
                "delete from public.solicitudes_union where conversacion_id in "
                f"('{grupo_1}', '{grupo_2}')",
                "delete from public.intereses_conversacion where conversacion_id in "
                f"('{grupo_1}', '{grupo_2}')",
                "delete from public.conversaciones where id in "
                f"('{conversacion_directa}', '{grupo_1}', '{grupo_2}')",
            ]
        )


async def _admin(statements: list[str]) -> None:
    from tests.conftest import run_admin_sql

    await run_admin_sql(statements)


async def _espera_violacion(sql: str, params: dict, fragmento: str) -> None:
    """La inserción debe fallar con una violación que mencione `fragmento`."""
    from Chatly.backend.database.session import get_session_factory

    with pytest.raises(IntegrityError) as excinfo:
        async with get_session_factory()() as session:
            await session.execute(text(sql), params)
            await session.commit()
    assert fragmento in str(excinfo.value)


async def test_fk_compuesta_rechaza_solicitud_a_conversacion_directa(
    entorno_social: dict,
) -> None:
    """`solicitudes_union` solo apunta a grupos: FK (conversacion_id, tipo)."""
    await _espera_violacion(
        "insert into public.solicitudes_union (conversacion_id, solicitante_id) "
        "values (:conversation_id, :user_id)",
        {"conversation_id": entorno_social["directa"], "user_id": entorno_social["b"]},
        "fk_solicitudes_union_grupo",
    )


async def test_dos_pendientes_globales_violan_unicidad(entorno_social: dict) -> None:
    """Una sola solicitud pendiente por usuario en toda la app (Q151)."""
    await _admin(
        [
            "insert into public.solicitudes_union (conversacion_id, solicitante_id) "
            f"values ('{entorno_social['grupo_1']}', '{entorno_social['b']}')"
        ]
    )
    await _espera_violacion(
        "insert into public.solicitudes_union (conversacion_id, solicitante_id) "
        "values (:conversation_id, :user_id)",
        {"conversation_id": entorno_social["grupo_2"], "user_id": entorno_social["b"]},
        "uq_solicitudes_union_pendiente_usuario",
    )


async def test_estado_invalido_viola_check(entorno_social: dict) -> None:
    await _espera_violacion(
        "insert into public.solicitudes_union "
        "(conversacion_id, solicitante_id, estado) "
        "values (:conversation_id, :user_id, 'bogus')",
        {"conversation_id": entorno_social["grupo_1"], "user_id": entorno_social["b"]},
        "ck_solicitudes_union_estado",
    )


async def test_rechazo_sin_motivo_viola_check(entorno_social: dict) -> None:
    """Un estado resuelto exige fecha y motivo de resolución."""
    await _espera_violacion(
        "insert into public.solicitudes_union "
        "(conversacion_id, solicitante_id, estado) "
        "values (:conversation_id, :user_id, 'rejected')",
        {"conversation_id": entorno_social["grupo_1"], "user_id": entorno_social["b"]},
        "ck_solicitudes_union_estado_resolucion",
    )


async def test_vence_en_por_defecto_es_14_dias(entorno_social: dict) -> None:
    """La caducidad acordada es de 14 días (Q160); el job llega en 0014."""
    from Chatly.backend.database.session import get_session_factory

    await _admin(
        [
            "insert into public.solicitudes_union (conversacion_id, solicitante_id) "
            f"values ('{entorno_social['grupo_1']}', '{entorno_social['c']}')"
        ]
    )
    async with get_session_factory()() as session:
        dias = (
            await session.execute(
                text(
                    "select extract(epoch from (vence_en - creada_en)) / 86400 "
                    "from public.solicitudes_union "
                    "where conversacion_id = :conversation_id "
                    "and solicitante_id = :user_id and estado = 'pending'"
                ),
                {
                    "conversation_id": entorno_social["grupo_1"],
                    "user_id": entorno_social["c"],
                },
            )
        ).scalar()
    assert dias == 14


async def test_group_has_capacity_con_grupo_nuevo(entorno_social: dict) -> None:
    """La función `SECURITY DEFINER` de 0013 responde capacidad disponible."""
    from Chatly.backend.database.session import get_session_factory

    async with get_session_factory()() as session:
        capacidad = (
            await session.execute(
                text("select app.group_has_capacity(:conversation_id)"),
                {"conversation_id": entorno_social["grupo_2"]},
            )
        ).scalar()
    assert capacidad is True


async def test_trigger_de_capacidad_esta_instalado(db_available) -> None:
    """El trigger de 0013 protege el máximo de 10 integrantes activos."""
    from Chatly.backend.database.session import get_session_factory

    async with get_session_factory()() as session:
        total = (
            await session.execute(
                text(
                    "select count(*) from pg_trigger "
                    "where tgname = 'trg_miembros_proteger_capacidad' "
                    "and tgrelid = 'public.miembros_conversacion'::regclass"
                )
            )
        ).scalar()
    assert total == 1


async def test_rls_de_solicitudes_exige_contexto_de_actor(
    entorno_social: dict,
) -> None:
    """Sin actor: 0 filas; con actor: el backend ve las solicitudes (§13)."""
    await require_app_role()
    await _admin(
        [
            "insert into public.solicitudes_union (conversacion_id, solicitante_id) "
            f"values ('{entorno_social['grupo_1']}', '{entorno_social['c']}')"
        ]
    )
    from Chatly.backend.database.session import get_test_session_factory

    async with get_test_session_factory()() as session:
        sin_actor = (
            await session.execute(text("select count(*) from public.solicitudes_union"))
        ).scalar_one()
    assert sin_actor == 0

    async with app_transaction(str(entorno_social["c"])) as session:
        con_actor = (
            await session.execute(
                text(
                    "select count(*) from public.solicitudes_union "
                    "where solicitante_id = :user_id and estado = 'pending'"
                ),
                {"user_id": entorno_social["c"]},
            )
        ).scalar_one()
    assert con_actor == 1
