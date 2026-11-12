"""identidad y rol de aplicación

Revision ID: 0005_identidad_rol
Revises: 0004_mensajes
Create Date: 2026-11-08

Hace que `app.current_actor_id()` sea `SECURITY DEFINER` para resolver
`auth.uid()` sin que `chatly_app` herede `authenticated`. Retira la herencia
del rol de aplicación y conserva los permisos explícitos de `0002_perfiles`.

No edita `0001_infra` porque esa revisión ya está aplicada. El rol que ejecuta
la migración debe tener `USAGE` sobre `auth` y `EXECUTE` sobre `auth.uid()`
(en este proyecto, `postgres`).
"""

from alembic import op

revision = "0005_identidad_rol"
down_revision = "0004_mensajes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create or replace function app.current_actor_id() returns uuid
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
          select coalesce(
            auth.uid(),
            nullif(current_setting('app.current_user_id', true), '')::uuid
          );
        $$;
        """
    )

    op.execute("revoke all on function app.current_actor_id() from public")

    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'grant execute on function app.current_actor_id() to authenticated';
          end if;
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant execute on function app.current_actor_id() to chatly_app';
            execute 'alter role chatly_app noinherit';
            execute 'revoke authenticated from chatly_app';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        create or replace function app.current_actor_id() returns uuid
        language sql stable as $$
          select coalesce(
            auth.uid(),
            nullif(current_setting('app.current_user_id', true), '')::uuid
          );
        $$;
        """
    )
    op.execute("grant execute on function app.current_actor_id() to public")

    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'grant authenticated to chatly_app';
          end if;
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'alter role chatly_app inherit';
          end if;
        end
        $$;
        """
    )
