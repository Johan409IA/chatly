"""infraestructura inicial: esquema app y función de identidad RLS

Revision ID: 0001_infra
Revises:
Create Date: 2026-11-03

Crea el esquema `app`, la función `app.current_actor_id()` compartida por las
políticas RLS y los grants al rol de aplicación `chatly_app` cuando exista.
El rol se crea manualmente desde el SQL editor de Supabase (requiere
privilegios elevados que la conexión de migraciones no tiene).
"""

from alembic import op

revision = "0001_infra"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create schema if not exists app")

    op.execute(
        """
        create or replace function app.current_actor_id() returns uuid
        language sql stable as $$
          select coalesce(
            auth.uid(),
            nullif(current_setting('app.current_user_id', true), '')::uuid
          );
        $$
        """
    )

    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant usage on schema app to chatly_app';
            execute 'grant execute on function app.current_actor_id() to chatly_app';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute("drop schema if exists app cascade")
