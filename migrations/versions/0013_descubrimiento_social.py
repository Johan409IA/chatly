"""descubrimiento social: descripción, descubribilidad, intereses de grupos
y solicitudes de unión

Revision ID: 0013_descubrimiento_social
Revises: 0008_auth_sync
Create Date: 2026-11-26

Aplica `docs/database-schema.md` §17.4–17.5 y §15 (fila `0013`):

- `conversaciones.descripcion` y `conversaciones.es_descubrible` con checks
  de descripción 10–300 y «descubrible solo grupos» (Q121, Q131).
- `uq_conversaciones_id_tipo (id, tipo)`, soporte de la FK compuesta que
  obliga a `solicitudes_union` a apuntar solo a grupos (Q158).
- `intereses_conversacion`: 1–5 intereses por grupo (el límite lo valida el
  servicio bloqueando la fila; la BD garantiza la relación N:M).
- `solicitudes_union`: estados `pending|accepted|rejected|expired`,
  `motivo_resolucion` con los siete valores del contrato, `vence_en` a
  14 días, índice único parcial de una sola solicitud pendiente global por
  usuario (Q151, Q159) y bandeja ordenada por llegada.
- `app.group_has_capacity(uuid)` `SECURITY DEFINER` y trigger que impide
  superar los diez integrantes activos de un grupo (Q8); completa lo que
  `0007_rls` dejó pendiente.
- RLS y grants de las dos tablas nuevas `TO chatly_app`: son tablas
  exclusivas del backend; el servicio aplica actor, visibilidad y membresía
  (`database-schema.md` §13, fila de tablas sociales).

La caducidad automática (`app.expire_pending_join_requests()` + job de
`pg_cron`) llega con `0014_social_cron` en la iteración 8: aquí la base ya
queda lista con `vence_en` y el índice de vencimiento (Q160).

Estilo idempotente de `0002`/`0005b`: objetos con `if not exists`, checks
envueltos en `do $$`, grants condicionados a que el rol exista.
"""

from alembic import op

revision = "0013_descubrimiento_social"
down_revision = "0008_auth_sync"
branch_labels = None
depends_on = None


def _add_check(table: str, name: str, condition: str) -> None:
    op.execute(
        f"""
        do $$
        begin
          if not exists (
            select 1 from pg_constraint
            where conname = '{name}' and conrelid = 'public.{table}'::regclass
          ) then
            alter table public.{table}
              add constraint {name} check ({condition});
          end if;
        end
        $$;
        """
    )


def upgrade() -> None:
    # 1) Descubribilidad del grupo (§17.4).
    op.execute(
        "alter table public.conversaciones"
        " add column if not exists descripcion text"
    )
    op.execute(
        "alter table public.conversaciones"
        " add column if not exists es_descubrible boolean not null default false"
    )
    _add_check(
        "conversaciones",
        "ck_conversaciones_descubribles_solo_grupos",
        "tipo = 'group' or (es_descubrible = false and descripcion is null)",
    )
    _add_check(
        "conversaciones",
        "ck_conversaciones_descripcion_publica",
        """
        es_descubrible = false
        or (descripcion is not null
            and char_length(btrim(descripcion)) between 10 and 300)
        """,
    )

    # Índice único (id, tipo): soporte de la FK compuesta de solicitudes.
    op.execute(
        "create unique index if not exists uq_conversaciones_id_tipo"
        " on public.conversaciones (id, tipo)"
    )

    # 2) Intereses de grupos (§17.4).
    op.execute(
        """
        create table if not exists public.intereses_conversacion (
            conversacion_id uuid        not null references public.conversaciones (id),
            interes_id      uuid        not null references public.intereses (id),
            creado_en       timestamptz not null default now(),

            primary key (conversacion_id, interes_id)
        )
        """
    )
    op.execute(
        "create index if not exists ix_intereses_conversacion_interes"
        " on public.intereses_conversacion (interes_id, conversacion_id)"
    )
    op.execute(
        "create index if not exists ix_conversaciones_descubribles"
        " on public.conversaciones (id)"
        " where tipo = 'group' and es_descubrible = true"
        "   and archivada = false and eliminado_en is null"
    )

    # 3) Solicitudes de unión (§17.5).
    op.execute(
        """
        create table if not exists public.solicitudes_union (
            id                uuid primary key default gen_random_uuid(),
            conversacion_id   uuid        not null,
            tipo              text        not null default 'group',
            solicitante_id    uuid        not null references public.perfiles (id),
            estado            text        not null default 'pending',
            motivo_resolucion text,
            creada_en         timestamptz not null default now(),
            vence_en          timestamptz not null default (now() + interval '14 days'),
            resuelta_en       timestamptz,
            resuelta_por      uuid        references public.perfiles (id),
            actualizado_en    timestamptz not null default now(),

            constraint ck_solicitudes_union_solo_grupos check (tipo = 'group'),
            constraint fk_solicitudes_union_grupo
                foreign key (conversacion_id, tipo)
                references public.conversaciones (id, tipo),
            constraint ck_solicitudes_union_estado
                check (estado in ('pending','accepted','rejected','expired')),
            constraint ck_solicitudes_union_motivo
                check (
                    motivo_resolucion is null
                    or motivo_resolucion in (
                        'accepted_by_admin',
                        'direct_add_same_group',
                        'rejected_by_admin',
                        'group_private',
                        'group_full',
                        'joined_other_group',
                        'expired'
                    )
                ),
            constraint ck_solicitudes_union_estado_resolucion
                check (
                    (estado = 'pending' and resuelta_en is null and motivo_resolucion is null)
                    or (estado <> 'pending'
                        and resuelta_en is not null and motivo_resolucion is not null)
                ),
            constraint ck_solicitudes_union_motivo_por_estado
                check (
                    (estado = 'pending' and motivo_resolucion is null)
                    or (estado = 'accepted' and motivo_resolucion in
                        ('accepted_by_admin','direct_add_same_group'))
                    or (estado = 'rejected' and motivo_resolucion in
                        ('rejected_by_admin','group_private','group_full','joined_other_group'))
                    or (estado = 'expired' and motivo_resolucion = 'expired')
                ),
            constraint ck_solicitudes_union_vencimiento
                check (vence_en > creada_en)
        )
        """
    )

    # Regla global: una sola solicitud pendiente por usuario en toda la app.
    op.execute(
        "create unique index if not exists uq_solicitudes_union_pendiente_usuario"
        " on public.solicitudes_union (solicitante_id)"
        " where estado = 'pending'"
    )
    # Bandeja del administrador: pendientes en orden de llegada.
    op.execute(
        "create index if not exists ix_solicitudes_union_pendientes_grupo"
        " on public.solicitudes_union (conversacion_id, creada_en, id)"
        " where estado = 'pending'"
    )
    # Caducidad: el job de pg_cron (0014) consulta vence_en.
    op.execute(
        "create index if not exists ix_solicitudes_union_vencimiento"
        " on public.solicitudes_union (vence_en)"
        " where estado = 'pending'"
    )
    # Periodo de espera: solo el rechazo manual cuenta (Q129, Q147).
    op.execute(
        "create index if not exists ix_solicitudes_union_rechazo_manual"
        " on public.solicitudes_union (solicitante_id, conversacion_id, resuelta_en desc)"
        " where estado = 'rejected' and motivo_resolucion = 'rejected_by_admin'"
    )

    # 4) Capacidad de grupos: máximo 10 integrantes activos (Q8); completa
    # lo que 0007_rls dejó pendiente. SECURITY DEFINER para contar todas las
    # filas aunque RLS oculte a otros miembros al rol que inserta.
    op.execute(
        """
        create or replace function app.group_has_capacity(p_conversacion_id uuid)
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select coalesce((
                select count(*) < 10
                from public.miembros_conversacion m
                where m.conversacion_id = p_conversacion_id
                  and m.salido_en is null
            ), true)
        $$;
        """
    )
    op.execute("revoke all on function app.group_has_capacity(uuid) from public")
    op.execute(
        """
        create or replace function public.proteger_capacidad_grupo()
        returns trigger
        language plpgsql
        security definer
        set search_path = public, pg_temp
        as $$
        begin
            if new.salido_en is not null then
                return new;
            end if;
            if not exists (
                select 1 from public.conversaciones c
                where c.id = new.conversacion_id and c.tipo = 'group'
            ) then
                return new;
            end if;
            if app.group_has_capacity(new.conversacion_id) then
                return new;
            end if;
            raise exception 'El grupo ya tiene el máximo de 10 integrantes.'
                using errcode = 'check_violation',
                      constraint = 'ck_miembros_capacidad_grupo';
        end
        $$;
        """
    )
    op.execute(
        "drop trigger if exists trg_miembros_proteger_capacidad"
        " on public.miembros_conversacion"
    )
    op.execute(
        """
        create trigger trg_miembros_proteger_capacidad
            before insert on public.miembros_conversacion
            for each row execute function public.proteger_capacidad_grupo()
        """
    )

    # 5) RLS: tablas solo-backend; el servicio aplica actor y membresía
    # (database-schema.md §13).
    for table in ("intereses_conversacion", "solicitudes_union"):
        op.execute(f"alter table public.{table} enable row level security")

    for table, policy, action in (
        ("intereses_conversacion", "intereses_conversacion_select_backend", "select"),
        ("intereses_conversacion", "intereses_conversacion_insert_backend", "insert"),
        ("intereses_conversacion", "intereses_conversacion_delete_backend", "delete"),
        ("solicitudes_union", "solicitudes_union_select_backend", "select"),
        ("solicitudes_union", "solicitudes_union_insert_backend", "insert"),
        ("solicitudes_union", "solicitudes_union_update_backend", "update"),
    ):
        op.execute(f"drop policy if exists {policy} on public.{table}")
        using_or_check = (
            f"for {action} to chatly_app"
            + (" using" if action in ("select", "delete") else " with check")
        )
        op.execute(
            f"""
            create policy {policy} on public.{table}
                {using_or_check} ((select app.current_actor_id()) is not null)
            """
        )

    # 6) Grants mínimos: solo si los roles existen en este entorno.
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant usage on schema app to chatly_app';
            execute 'grant execute on function app.group_has_capacity(uuid)'
                    ' to chatly_app';
            execute 'grant select, insert, delete'
                    ' on public.intereses_conversacion to chatly_app';
            execute 'grant select, insert, update'
                    ' on public.solicitudes_union to chatly_app';
          end if;
          if exists (select 1 from pg_roles where rolname = 'anon') then
            execute 'revoke all on public.intereses_conversacion from anon';
            execute 'revoke all on public.solicitudes_union from anon';
          end if;
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'revoke all on public.intereses_conversacion from authenticated';
            execute 'revoke all on public.solicitudes_union from authenticated';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "drop trigger if exists trg_miembros_proteger_capacidad"
        " on public.miembros_conversacion"
    )
    op.execute("drop function if exists public.proteger_capacidad_grupo()")
    op.execute("drop function if exists app.group_has_capacity(uuid)")

    op.execute("drop table if exists public.solicitudes_union cascade")
    op.execute("drop table if exists public.intereses_conversacion cascade")
    op.execute("drop index if exists ix_conversaciones_descubribles")
    op.execute("drop index if exists uq_conversaciones_id_tipo")
    op.execute(
        "alter table public.conversaciones"
        " drop column if exists es_descubrible,"
        " drop column if exists descripcion"
    )
