"""registros de auditoría

Revision ID: 0006_auditoria
Revises: 0005b_intereses
Create Date: 2026-11-15

Crea `registros_auditoria` y su acceso mínimo antes de las políticas de chat:
enviar, editar y eliminar mensajes escribe auditoría en la misma transacción,
así que la tabla debe existir cuando la mensajería empieza a implementarse.

Diseño: `docs/database-schema.md` §12 y `docs/authorization-matrix.md` §5.12.
Sin claves foráneas: la auditoría sobrevive a cualquier cambio de estado.
Solo inserción; no se conceden `select`, `update` ni `delete` a la aplicación.

Orden de migraciones (ver `docs/database-schema.md` §15): el bloque de
auditoría, RLS y sincronización de verificación se adelanta al principio de la
cadena para desbloquear la API de conversaciones. Ninguna de las revisiones
movidas se había aplicado (`alembic_version` estaba en `0005b_intereses`), así
que renumerarlas no rompe entornos existentes.
"""

from alembic import op

revision = "0006_auditoria"
down_revision = "0005b_intereses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists public.registros_auditoria (
            id                 bigint generated always as identity primary key,
            actor_id           uuid,
            accion             text        not null,
            tipo_entidad       text        not null,
            entidad_id         uuid,
            conversacion_id    uuid,
            valores_anteriores jsonb,
            valores_nuevos     jsonb,
            creado_en          timestamptz not null default now(),

            constraint ck_auditoria_accion check (char_length(btrim(accion)) > 0),
            constraint ck_auditoria_entidad check (char_length(btrim(tipo_entidad)) > 0)
        )
        """
    )

    op.execute(
        "create index if not exists ix_auditoria_entidad"
        " on public.registros_auditoria (tipo_entidad, entidad_id, creado_en desc)"
    )
    op.execute(
        "create index if not exists ix_auditoria_actor"
        " on public.registros_auditoria (actor_id, creado_en desc)"
    )
    op.execute(
        "create index if not exists ix_auditoria_conversacion"
        " on public.registros_auditoria (conversacion_id, creado_en desc)"
    )

    op.execute("alter table public.registros_auditoria enable row level security")
    op.execute("drop policy if exists auditoria_insert_backend on public.registros_auditoria")
    op.execute(
        """
        create policy auditoria_insert_backend on public.registros_auditoria
            for insert to chatly_app
            with check (
                actor_id is null
                or actor_id = (select app.current_actor_id())
            )
        """
    )

    # Grants mínimos: solo inserción. `actor_id is null` queda reservado a
    # operaciones automáticas controladas (expiración de solicitudes).
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant usage on schema app to chatly_app';
            execute 'grant insert on public.registros_auditoria to chatly_app';
            execute 'revoke select, update, delete, truncate'
                    ' on public.registros_auditoria from chatly_app';
          end if;
          if exists (select 1 from pg_roles where rolname = 'anon') then
            execute 'revoke all on public.registros_auditoria from anon';
          end if;
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'revoke all on public.registros_auditoria from authenticated';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute("drop policy if exists auditoria_insert_backend on public.registros_auditoria")
    op.execute("drop table if exists public.registros_auditoria cascade")
