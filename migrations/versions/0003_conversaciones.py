"""conversaciones, miembros y preferencias

Revision ID: 0003_conversaciones
Revises: 0002_perfiles
Create Date: 2026-11-08

Crea el núcleo de conversaciones privadas y grupales, los periodos de
membresía y las preferencias individuales de ocultación. Las políticas RLS
se incorporan en `0007_rls`.
"""

from alembic import op

revision = "0003_conversaciones"
down_revision = "0002_perfiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists public.conversaciones (
            id                    uuid primary key default gen_random_uuid(),
            tipo                  text        not null,
            nombre                text,
            creado_por            uuid        not null references public.perfiles (id),
            administrador_id      uuid        references public.perfiles (id),
            usuario_directo_menor uuid        references public.perfiles (id),
            usuario_directo_mayor uuid        references public.perfiles (id),
            archivada             boolean     not null default false,
            archivada_en          timestamptz,
            ultimo_mensaje_en     timestamptz,
            eliminado_en          timestamptz,
            creado_en             timestamptz not null default now(),
            actualizado_en        timestamptz not null default now(),

            constraint ck_conversaciones_tipo check (tipo in ('direct','group')),
            constraint ck_conversaciones_forma check (
                (tipo = 'direct'
                    and usuario_directo_menor is not null
                    and usuario_directo_mayor is not null
                    and usuario_directo_menor < usuario_directo_mayor
                    and nombre is null)
                or
                (tipo = 'group'
                    and usuario_directo_menor is null
                    and usuario_directo_mayor is null
                    and nombre is not null)
            ),
            constraint ck_conversaciones_nombre_grupo check (
                tipo <> 'group' or char_length(btrim(nombre)) between 3 and 40
            ),
            constraint ck_conversaciones_archivo check (
                (archivada and archivada_en is not null)
                or (not archivada and archivada_en is null)
            )
        )
        """
    )

    op.execute(
        "create unique index if not exists uq_conversaciones_par_directo"
        " on public.conversaciones (usuario_directo_menor, usuario_directo_mayor)"
        " where tipo = 'direct'"
    )
    op.execute(
        "create index if not exists ix_conversaciones_actividad"
        " on public.conversaciones (ultimo_mensaje_en desc nulls last)"
        " where eliminado_en is null"
    )
    op.execute(
        "create index if not exists ix_conversaciones_creado_por"
        " on public.conversaciones (creado_por)"
    )
    op.execute(
        "create index if not exists ix_conversaciones_administrador"
        " on public.conversaciones (administrador_id)"
    )

    op.execute(
        """
        create table if not exists public.miembros_conversacion (
            id                      uuid primary key default gen_random_uuid(),
            conversacion_id         uuid        not null
                                    references public.conversaciones (id) on delete cascade,
            usuario_id              uuid        not null references public.perfiles (id),
            rol                     text        not null default 'member',
            estado                  text        not null default 'active',
            unido_en                timestamptz not null default now(),
            salido_en               timestamptz,
            agregado_por            uuid        references public.perfiles (id),
            retirado_por            uuid        references public.perfiles (id),
            ultimo_mensaje_leido_id uuid,
            ultimo_leido_en         timestamptz,
            creado_en               timestamptz not null default now(),
            actualizado_en          timestamptz not null default now(),

            constraint ck_miembros_rol check (rol in ('admin','member')),
            constraint ck_miembros_estado check (estado in ('active','left','removed')),
            constraint ck_miembros_periodo check (
                (salido_en is null and estado = 'active')
                or (salido_en is not null and estado in ('left','removed'))
            ),
            constraint ck_miembros_salida check (salido_en is null or salido_en >= unido_en)
        )
        """
    )

    op.execute(
        "create unique index if not exists uq_miembros_activos"
        " on public.miembros_conversacion (conversacion_id, usuario_id)"
        " where salido_en is null"
    )
    op.execute(
        "create unique index if not exists uq_miembros_un_admin"
        " on public.miembros_conversacion (conversacion_id)"
        " where rol = 'admin' and salido_en is null"
    )
    op.execute(
        "create index if not exists ix_miembros_usuario_periodo"
        " on public.miembros_conversacion (usuario_id, conversacion_id, unido_en)"
    )
    op.execute(
        "create index if not exists ix_miembros_conversacion"
        " on public.miembros_conversacion (conversacion_id, unido_en)"
    )
    op.execute(
        "create index if not exists ix_miembros_busqueda_politica"
        " on public.miembros_conversacion (conversacion_id, usuario_id, unido_en)"
        " include (salido_en)"
    )
    op.execute(
        "create index if not exists ix_miembros_ultimo_leido"
        " on public.miembros_conversacion (conversacion_id, usuario_id, ultimo_leido_en)"
    )

    op.execute(
        """
        create table if not exists public.preferencias_conversacion (
            conversacion_id uuid        not null
                            references public.conversaciones (id) on delete cascade,
            usuario_id      uuid        not null references public.perfiles (id),
            oculta          boolean     not null default false,
            ocultada_en     timestamptz,
            creado_en       timestamptz not null default now(),
            actualizado_en  timestamptz not null default now(),

            primary key (conversacion_id, usuario_id),
            constraint ck_preferencias_ocultada_en check (oculta = (ocultada_en is not null))
        )
        """
    )

    op.execute(
        "create index if not exists ix_preferencias_usuario_oculta"
        " on public.preferencias_conversacion (usuario_id, oculta)"
    )

    for table in ("conversaciones", "miembros_conversacion", "preferencias_conversacion"):
        op.execute(f"drop trigger if exists trg_{table}_actualizado on public.{table}")
        op.execute(
            f"""
            create trigger trg_{table}_actualizado
                before update on public.{table}
                for each row execute function public.tocar_actualizado_en()
            """
        )


def downgrade() -> None:
    for table in ("preferencias_conversacion", "miembros_conversacion", "conversaciones"):
        op.execute(f"drop trigger if exists trg_{table}_actualizado on public.{table}")
    op.execute("drop table if exists public.preferencias_conversacion cascade")
    op.execute("drop table if exists public.miembros_conversacion cascade")
    op.execute("drop table if exists public.conversaciones cascade")
