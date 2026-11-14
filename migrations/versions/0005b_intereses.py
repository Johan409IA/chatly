"""catálogo de intereses y selección en el registro

Revision ID: 0005b_intereses
Revises: 0005a_alias_exists
Create Date: 2026-11-12

Crea el catálogo de intereses (`categorias_interes`, `intereses`), la relación
de selección personal (`intereses_usuario`) y la bandera de visibilidad
pública del perfil. El catálogo se expone sin sesión mediante la función
`app.catalogo_intereses()` `SECURITY DEFINER`, igual que `app.alias_exists`:
el registro lo consulta antes de que exista cuenta (Q15, Q178).

Las políticas RLS del catálogo siguen exigiendo actor (`authorization-matrix`
§6.1); la función pública es la que permite leerlo sin actor. La política de
lectura de intereses de terceros no se crea aquí: depende de
`app.is_verified_actor()`, que llega con `0013_descubrimiento_social`.

Estilo idempotente de `0002_perfiles`: los objetos se crean solo si no
existen y los grants se aplican con `do $$ ... $$` para no fallar cuando el
rol no existe en el entorno.

Fuente de verdad del DDL: `docs/database-schema.md` §17.1–17.3.
"""

from alembic import op

revision = "0005b_intereses"
down_revision = "0005a_alias_exists"
branch_labels = None
depends_on = None

# Catálogo inicial (database-schema.md:974). Categorías en orden 1..5.
_CATEGORIAS = (
    ("Tecnología", 1),
    ("Negocios", 2),
    ("Diseño", 3),
    ("Entretenimiento", 4),
    ("Deportes", 5),
)

_INTERESES = (
    ("Tecnología", "Programación"),
    ("Tecnología", "IA"),
    ("Tecnología", "Ciberseguridad"),
    ("Tecnología", "Desarrollo web"),
    ("Negocios", "Marketing"),
    ("Negocios", "Ventas"),
    ("Negocios", "Emprendimiento"),
    ("Diseño", "UI/UX"),
    ("Diseño", "Diseño gráfico"),
    ("Diseño", "Ilustración"),
    ("Entretenimiento", "Música"),
    ("Entretenimiento", "Cine"),
    ("Entretenimiento", "Videojuegos"),
    ("Deportes", "Fútbol"),
    ("Deportes", "Baloncesto"),
    ("Deportes", "Fitness"),
)


def upgrade() -> None:
    # 1) Catálogo: categorías e intereses.
    op.execute(
        """
        create table if not exists public.categorias_interes (
            id              uuid primary key default gen_random_uuid(),
            nombre          text        not null,
            orden           integer     not null default 0,
            activa          boolean     not null default true,
            creado_en       timestamptz not null default now(),
            actualizado_en  timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        create table if not exists public.intereses (
            id              uuid primary key default gen_random_uuid(),
            categoria_id    uuid        not null references public.categorias_interes (id),
            nombre          text        not null,
            activo          boolean     not null default true,
            creado_en       timestamptz not null default now(),
            actualizado_en  timestamptz not null default now()
        )
        """
    )

    for table, name in (
        ("categorias_interes", "ck_categorias_interes_nombre"),
        ("intereses", "ck_intereses_nombre"),
    ):
        op.execute(
            f"""
            do $$
            begin
              if not exists (
                select 1 from pg_constraint
                where conname = '{name}' and conrelid = 'public.{table}'::regclass
              ) then
                alter table public.{table}
                  add constraint {name} check (char_length(btrim(nombre)) > 0);
              end if;
            end
            $$;
            """
        )

    op.execute(
        "create unique index if not exists uq_categorias_interes_nombre"
        " on public.categorias_interes (lower(btrim(nombre)))"
    )
    op.execute(
        "create unique index if not exists uq_intereses_nombre"
        " on public.intereses (lower(btrim(nombre)))"
    )
    op.execute(
        "create index if not exists ix_intereses_categoria_activos"
        " on public.intereses (categoria_id, nombre) where activo = true"
    )

    # 2) Selección personal de intereses.
    op.execute(
        """
        create table if not exists public.intereses_usuario (
            usuario_id  uuid        not null references public.perfiles (id) on delete cascade,
            interes_id  uuid        not null references public.intereses (id),
            creado_en   timestamptz not null default now(),
            primary key (usuario_id, interes_id)
        )
        """
    )
    op.execute(
        "create index if not exists ix_intereses_usuario_interes"
        " on public.intereses_usuario (interes_id, usuario_id)"
    )

    # 3) Semilla del catálogo (idempotente por nombre).
    categorias = ", ".join(f"('{nombre}', {orden})" for nombre, orden in _CATEGORIAS)
    op.execute(
        f"""
        insert into public.categorias_interes (nombre, orden)
        select v.nombre, v.orden
        from (values {categorias}) as v(nombre, orden)
        where not exists (
            select 1 from public.categorias_interes c
            where lower(btrim(c.nombre)) = lower(btrim(v.nombre))
        )
        """
    )
    intereses = ", ".join(f"('{categoria}', '{nombre}')" for categoria, nombre in _INTERESES)
    op.execute(
        f"""
        insert into public.intereses (categoria_id, nombre)
        select c.id, v.nombre
        from (values {intereses}) as v(categoria, nombre)
        join public.categorias_interes c
          on lower(btrim(c.nombre)) = lower(btrim(v.categoria))
        where not exists (
            select 1 from public.intereses i
            where lower(btrim(i.nombre)) = lower(btrim(v.nombre))
        )
        """
    )

    # 4) Visibilidad pública del perfil (database-schema.md §17.1).
    op.execute(
        "alter table public.perfiles"
        " add column if not exists visibilidad_publica boolean not null default true"
    )
    op.execute(
        "create index if not exists ix_perfiles_visibles_descubrimiento"
        " on public.perfiles (id)"
        " where eliminado_en is null and visibilidad_publica = true"
    )
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
            p.creado_en,
            p.visibilidad_publica
        from public.perfiles p
        where p.eliminado_en is null
        """
    )

    # 5) Catálogo público sin actor (mismo patrón que app.alias_exists).
    op.execute(
        """
        create or replace function app.catalogo_intereses()
        returns table (
            categoria_id uuid,
            categoria text,
            categoria_orden int,
            interes_id uuid,
            interes text
        )
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select c.id, c.nombre, c.orden, i.id, i.nombre
            from public.categorias_interes c
            join public.intereses i on i.categoria_id = c.id
            where c.activa = true and i.activo = true
            order by c.orden, lower(c.nombre), lower(i.nombre)
        $$;
        """
    )
    op.execute("revoke all on function app.catalogo_intereses() from public")

    # 6) RLS y políticas (authorization-matrix §6.1 y §6.2).
    for table in ("categorias_interes", "intereses", "intereses_usuario"):
        op.execute(f"alter table public.{table} enable row level security")

    for table, policy in (
        ("categorias_interes", "categorias_select_activas_backend"),
        ("intereses", "intereses_select_activos_backend"),
        ("intereses_usuario", "intereses_usuario_select_propio"),
        ("intereses_usuario", "intereses_usuario_insert_propio"),
        ("intereses_usuario", "intereses_usuario_delete_propio"),
    ):
        op.execute(f"drop policy if exists {policy} on public.{table}")

    op.execute(
        """
        create policy categorias_select_activas_backend on public.categorias_interes
            for select to chatly_app
            using (activa = true and (select app.current_actor_id()) is not null)
        """
    )
    op.execute(
        """
        create policy intereses_select_activos_backend on public.intereses
            for select to chatly_app
            using (
                activo = true
                and exists (
                    select 1
                    from public.categorias_interes c
                    where c.id = categoria_id
                      and c.activa = true
                )
                and (select app.current_actor_id()) is not null
            )
        """
    )
    op.execute(
        """
        create policy intereses_usuario_select_propio on public.intereses_usuario
            for select to chatly_app
            using (usuario_id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy intereses_usuario_insert_propio on public.intereses_usuario
            for insert to chatly_app
            with check (usuario_id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy intereses_usuario_delete_propio on public.intereses_usuario
            for delete to chatly_app
            using (usuario_id = (select app.current_actor_id()))
        """
    )

    # 7) Grants mínimos: solo si los roles existen en este entorno.
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant usage on schema app to chatly_app';
            execute 'grant execute on function app.catalogo_intereses() to chatly_app';
            execute 'grant select on public.categorias_interes to chatly_app';
            execute 'grant select on public.intereses to chatly_app';
            execute 'grant select, insert, delete on public.intereses_usuario to chatly_app';
          end if;
          if exists (select 1 from pg_roles where rolname = 'anon') then
            execute 'revoke all on public.categorias_interes from anon';
            execute 'revoke all on public.intereses from anon';
            execute 'revoke all on public.intereses_usuario from anon';
          end if;
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'revoke all on public.categorias_interes from authenticated';
            execute 'revoke all on public.intereses from authenticated';
            execute 'revoke all on public.intereses_usuario from authenticated';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute("drop function if exists app.catalogo_intereses()")
    op.execute("drop table if exists public.intereses_usuario cascade")
    op.execute("drop table if exists public.intereses cascade")
    op.execute("drop table if exists public.categorias_interes cascade")

    # La vista de 0002 no conoce `visibilidad_publica`: se recrea (no se puede
    # quitar una columna con `create or replace view`) antes de eliminar la
    # columna.
    op.execute("drop view if exists app.perfiles_publicos")
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
    op.execute("drop index if exists ix_perfiles_visibles_descubrimiento")
    op.execute("alter table public.perfiles drop column if exists visibilidad_publica")
