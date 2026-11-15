"""sincronización de `perfiles.correo_verificado_en`

Revision ID: 0008_auth_sync
Revises: 0007_rls
Create Date: 2026-11-15

`correo_verificado_en` es la fuente que consultan `app.is_verified_actor()` y
la guarda `require_verified_actor` para bloquear el chat a cuentas sin
confirmar (Q15). Hasta esta revisión la columna existía en `0002_perfiles`
pero nadie la escribía, así que `app.is_verified_actor()` devolvía `false` para
todos y el chat habría quedado cerrado incluso para usuarios confirmados.

Se adelanta desde el final de la cadena porque `0007_rls` ya depende de ella:
las políticas de conversaciones, miembros y mensajes evalúan
`app.is_verified_actor()`.

Contenido:

1. Trigger `after insert or update of email_confirmed_at` sobre `auth.users`
   que copia el valor a `public.perfiles`. Solo si `auth.users` existe: en una
   base local sin Supabase Auth el bloque se omite y el esquema sigue siendo
   aplicable.
2. Backfill de los perfiles ya confirmados.

`auth.users` es gestionado por Supabase Auth: esta migración no altera sus
columnas, solo añade un trigger. El `downgrade` lo retira y deja la columna con
sus valores (no se destruyen datos de verificación).
"""

from alembic import op

revision = "0008_auth_sync"
down_revision = "0007_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La función vive en `app` aunque el trigger se cree en `auth`: así el
    # cuerpo queda en un esquema propio y con `search_path` fijo.
    op.execute(
        """
        create or replace function app.sincronizar_correo_verificado()
        returns trigger
        language plpgsql
        security definer
        set search_path = public, pg_temp
        as $$
        begin
            update public.perfiles
               set correo_verificado_en = new.email_confirmed_at
             where id = new.id
               and correo_verificado_en is distinct from new.email_confirmed_at;
            return new;
        end $$;
        """
    )

    op.execute(
        """
        do $$
        begin
          if exists (
            select 1 from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'auth' and c.relname = 'users' and c.relkind = 'r'
          ) then
            execute 'drop trigger if exists trg_auth_users_correo_verificado'
                    ' on auth.users';
            execute 'create trigger trg_auth_users_correo_verificado'
                    ' after insert or update of email_confirmed_at on auth.users'
                    ' for each row execute function app.sincronizar_correo_verificado()';

            -- Backfill: usuarios que ya habían confirmado antes de esta revisión.
            execute 'update public.perfiles p'
                    ' set correo_verificado_en = u.email_confirmed_at'
                    ' from auth.users u'
                    ' where u.id = p.id'
                    '   and u.email_confirmed_at is not null'
                    '   and p.correo_verificado_en is null';
          end if;
        end
        $$;
        """
    )

    op.execute("revoke all on function app.sincronizar_correo_verificado() from public")


def downgrade() -> None:
    op.execute(
        """
        do $$
        begin
          if exists (
            select 1 from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'auth' and c.relname = 'users' and c.relkind = 'r'
          ) then
            execute 'drop trigger if exists trg_auth_users_correo_verificado on auth.users';
          end if;
        end
        $$;
        """
    )
    op.execute("drop function if exists app.sincronizar_correo_verificado()")
