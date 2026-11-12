"""perfiles y contactos_usuario

Revision ID: 0002_perfiles
Revises: 0001_infra
Create Date: 2026-11-05

Crea el perfil público 1:1 con `auth.users`, sus contactos normalizados, la
vista `app.perfiles_publicos`, la búsqueda por correo y las políticas RLS en
español (AGENTS.md).

Idempotente: las tablas ya se habían creado con SQL manual en Supabase. Cada
objeto se crea solo si no existe, de modo que `alembic upgrade head` deja el
esquema consistente sin borrar datos.
"""

from alembic import op

revision = "0002_perfiles"
down_revision = "0001_infra"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Perfiles: 1:1 con auth.users.
    op.execute(
        """
        create table if not exists public.perfiles (
            id                   uuid primary key references auth.users (id) on delete cascade,
            alias                text        not null,
            nombre_visible       text        not null,
            ruta_avatar          text,
            fecha_nacimiento     date        not null,
            genero               text        not null,
            correo_verificado_en timestamptz,
            alias_cambiado_en    timestamptz,
            eliminado_en         timestamptz,
            creado_en            timestamptz not null default now(),
            actualizado_en       timestamptz not null default now()
        )
        """
    )

    # Constraints: se añaden solo si faltan (el SQL manual pudo omitirlas).
    for name, definition in (
        ("ck_perfiles_formato_alias", "check (alias ~ '^[a-z][a-z0-9_]{2,19}$')"),
        ("ck_perfiles_alias_minusculas", "check (alias = lower(alias))"),
        (
            "ck_perfiles_longitud_nombre",
            "check (char_length(btrim(nombre_visible)) between 2 and 60)",
        ),
        ("ck_perfiles_genero", "check (genero in ('femenino', 'masculino'))"),
        (
            "ck_perfiles_fecha_plausible",
            "check (fecha_nacimiento between date '1900-01-01' and date '2100-12-31')",
        ),
    ):
        op.execute(
            f"""
            do $$
            begin
              if not exists (
                select 1 from pg_constraint
                where conname = '{name}' and conrelid = 'public.perfiles'::regclass
              ) then
                alter table public.perfiles add constraint {name} {definition};
              end if;
            end
            $$;
            """
        )

    op.execute(
        "create unique index if not exists uq_perfiles_alias on public.perfiles (lower(alias))"
    )
    op.execute(
        "create index if not exists ix_perfiles_alias_prefijo"
        " on public.perfiles (lower(alias) text_pattern_ops)"
        " where eliminado_en is null"
    )
    op.execute(
        "create index if not exists ix_perfiles_activos"
        " on public.perfiles (id) where eliminado_en is null"
    )

    # 2) Contactos: correo normalizado, nunca devuelto al cliente.
    op.execute(
        """
        create table if not exists public.contactos_usuario (
            usuario_id         uuid primary key
                               references public.perfiles (id) on delete cascade,
            correo_normalizado text        not null,
            creado_en          timestamptz not null default now(),
            actualizado_en     timestamptz not null default now()
        )
        """
    )

    for name, definition in (
        (
            "ck_contactos_correo_minusculas",
            "check (correo_normalizado = lower(btrim(correo_normalizado)))",
        ),
        (
            "uq_contactos_correo",
            "unique (correo_normalizado)",
        ),
    ):
        op.execute(
            f"""
            do $$
            begin
              if not exists (
                select 1 from pg_constraint
                where conname = '{name}'
                  and conrelid = 'public.contactos_usuario'::regclass
              ) then
                alter table public.contactos_usuario add constraint {name} {definition};
              end if;
            end
            $$;
            """
        )

    # 3) Edad 18–120: los check no admiten current_date; se valida con trigger.
    op.execute(
        """
        create or replace function public.validar_fecha_nacimiento_perfil()
        returns trigger language plpgsql as $$
        declare
            v_edad int := date_part('year', age(current_date, new.fecha_nacimiento))::int;
        begin
            if new.fecha_nacimiento > current_date then
                raise exception 'La fecha de nacimiento no puede ser futura'
                    using errcode = '23514';
            end if;
            if v_edad < 18 or v_edad > 120 then
                raise exception 'La edad debe estar entre 18 y 120 años'
                    using errcode = '23514';
            end if;
            return new;
        end $$;
        """
    )
    op.execute("drop trigger if exists trg_perfiles_fecha_nacimiento on public.perfiles")
    op.execute(
        """
        create trigger trg_perfiles_fecha_nacimiento
            before insert or update of fecha_nacimiento on public.perfiles
            for each row execute function public.validar_fecha_nacimiento_perfil()
        """
    )

    # 4) actualizado_en automático.
    op.execute(
        """
        create or replace function public.tocar_actualizado_en()
        returns trigger language plpgsql as $$
        begin
            new.actualizado_en := now();
            return new;
        end $$;
        """
    )
    op.execute("drop trigger if exists trg_perfiles_actualizado on public.perfiles")
    op.execute(
        """
        create trigger trg_perfiles_actualizado before update on public.perfiles
            for each row execute function public.tocar_actualizado_en()
        """
    )
    op.execute("drop trigger if exists trg_contactos_actualizado on public.contactos_usuario")
    op.execute(
        """
        create trigger trg_contactos_actualizado before update on public.contactos_usuario
            for each row execute function public.tocar_actualizado_en()
        """
    )

    # 5) Vista con edad calculada (la edad no se almacena).
    op.execute(
        """
        create or replace view app.perfiles_publicos
        with (security_invoker = true) as
        select
            p.id,
            p.alias,
            p.nombre_visible,
            p.ruta_avatar,
            date_part('year', age(current_date, p.fecha_nacimiento))::int as edad,
            p.genero,
            p.creado_en
        from public.perfiles p
        where p.eliminado_en is null
        """
    )

    # 6) Búsqueda exacta por correo: solo devuelve datos públicos.
    op.execute(
        """
        create or replace function app.buscar_usuario_por_correo(p_correo text)
        returns table (
            usuario_id uuid,
            alias text,
            nombre_visible text,
            ruta_avatar text
        )
        language sql
        security definer
        set search_path = app, public, pg_temp
        as $$
            select p.id, p.alias, p.nombre_visible, p.ruta_avatar
            from public.contactos_usuario c
            join public.perfiles p on p.id = c.usuario_id
            where app.current_actor_id() is not null
              and p.id <> app.current_actor_id()
              and c.correo_normalizado = lower(btrim(p_correo))
              and p.eliminado_en is null;
        $$;
        """
    )
    op.execute("revoke all on function app.buscar_usuario_por_correo(text) from public")

    # 7) RLS y políticas.
    op.execute("alter table public.perfiles enable row level security")
    op.execute("alter table public.contactos_usuario enable row level security")

    for table, policy in (
        ("perfiles", "perfiles_lectura_backend"),
        ("perfiles", "perfiles_alta_propia"),
        ("perfiles", "perfiles_actualizacion_propia"),
        ("contactos_usuario", "contactos_alta_backend"),
        ("contactos_usuario", "contactos_actualizacion_backend"),
    ):
        op.execute(f"drop policy if exists {policy} on public.{table}")

    op.execute(
        """
        create policy perfiles_lectura_backend on public.perfiles
            for select to chatly_app
            using ((select app.current_actor_id()) is not null)
        """
    )
    op.execute(
        """
        create policy perfiles_alta_propia on public.perfiles
            for insert to chatly_app
            with check (id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy perfiles_actualizacion_propia on public.perfiles
            for update to chatly_app
            using (id = (select app.current_actor_id()))
            with check (id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy contactos_alta_backend on public.contactos_usuario
            for insert to chatly_app
            with check (usuario_id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy contactos_actualizacion_backend on public.contactos_usuario
            for update to chatly_app
            using (usuario_id = (select app.current_actor_id()))
            with check (usuario_id = (select app.current_actor_id()))
        """
    )

    # 8) Grants mínimos: solo si los roles existen en este entorno.
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant usage on schema app to chatly_app';
            execute 'grant execute on function app.current_actor_id() to chatly_app';
            execute 'grant select, insert, update on public.perfiles to chatly_app';
            execute 'grant insert, update on public.contactos_usuario to chatly_app';
            execute 'grant execute on function app.buscar_usuario_por_correo(text)'
                    ' to chatly_app';
          end if;
          if exists (select 1 from pg_roles where rolname = 'anon') then
            execute 'revoke all on public.perfiles from anon';
            execute 'revoke all on public.contactos_usuario from anon';
          end if;
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'revoke all on public.perfiles from authenticated';
            execute 'revoke all on public.contactos_usuario from authenticated';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute("drop view if exists app.perfiles_publicos")
    op.execute("drop function if exists app.buscar_usuario_por_correo(text)")
    op.execute("drop table if exists public.contactos_usuario cascade")
    op.execute("drop table if exists public.perfiles cascade")
    op.execute("drop function if exists public.validar_fecha_nacimiento_perfil()")
    op.execute("drop function if exists public.tocar_actualizado_en()")
