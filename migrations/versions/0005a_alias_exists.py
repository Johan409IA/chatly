"""comprobación de alias para el registro

Revision ID: 0005a_alias_exists
Revises: 0005_identidad_rol
Create Date: 2026-11-08

Permite comprobar si un alias está ocupado antes de crear la cuenta en
Supabase Auth. La función es `SECURITY DEFINER` y solo devuelve un booleano,
así que `chatly_app` no necesita leer `perfiles` sin contexto de actor.
"""

from alembic import op

revision = "0005a_alias_exists"
down_revision = "0005_identidad_rol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create or replace function app.alias_exists(p_alias text)
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select exists (
                select 1
                from public.perfiles p
                where lower(p.alias) = lower(btrim(p_alias))
                  and p.eliminado_en is null
            );
        $$;
        """
    )
    op.execute("revoke all on function app.alias_exists(text) from public")

    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant execute on function app.alias_exists(text) to chatly_app';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute("drop function if exists app.alias_exists(text)")
