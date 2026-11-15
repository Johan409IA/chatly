"""políticas RLS del chat, funciones de autorización y grants

Revision ID: 0007_rls
Revises: 0006_auditoria
Create Date: 2026-11-15

Implementa la autorización de conversaciones y mensajes antes de que la API
empiece a consultarlos:

1. Funciones `SECURITY DEFINER` de `app` (identidad, verificación, membresía y
   periodos). Sin ellas las políticas se evalúan con RLS activa y se produciría
   recursión.
2. Políticas RLS de `conversaciones`, `miembros_conversacion`,
   `preferencias_conversacion`, `mensajes`, `versiones_mensaje` y
   `reacciones_mensaje`.
3. Grants por tabla en la misma revisión: con RLS activa y sin `GRANT` la app
   recibe `42501`, y con `GRANT` y sin políticas recibe cero filas. Ambas capas
   son obligatorias, así que separarlas solo abre una ventana en la que el
   backend no puede consultar nada.

Fuente: `docs/authorization-matrix.md` §3.1–3.3 y §5.3–5.8.

Pendiente para `0013_descubrimiento_social` (dependen de columnas que aún no
existen): `conversaciones_select_backend_descubribles`, `app.group_has_capacity`
y `app.discoverable_group_member_count`, que usan `conversaciones.es_descubrible`
y `conversaciones.descripcion`.
"""

from alembic import op

revision = "0007_rls"
down_revision = "0006_auditoria"
branch_labels = None
depends_on = None

_FUNCTIONS = (
    "app.is_verified_actor()",
    "app.has_membership(uuid)",
    "app.has_period(uuid, timestamptz)",
    "app.is_active_member(uuid)",
    "app.is_active_admin(uuid)",
    "app.can_bootstrap_membership(uuid, uuid)",
)

_TABLES = (
    ("conversaciones", "conversaciones"),
    ("miembros_conversacion", "miembros"),
    ("preferencias_conversacion", "preferencias"),
    ("mensajes", "mensajes"),
    ("versiones_mensaje", "versiones"),
    ("reacciones_mensaje", "reacciones"),
)

# Una sola lista para el `drop` defensivo del upgrade y para el downgrade: si
# se duplican, se desincronizan y una política sobrevive a la bajada.
_POLICY_SUFFIXES = (
    "select_realtime_activo",
    "select_realtime_activos",
    "select_backend",
    "select_backend_membresia",
    "select_backend_autor",
    "select_por_periodo",
    "select_propio",
    "insert_backend",
    "insert_backend_autor",
    "insert_propia",
    "insert_propio",
    "update_admin",
    "update_backend",
    "update_propio",
    "update_propia",
)


def upgrade() -> None:
    # 1) Funciones de autorización (authorization-matrix §3.1–3.3).
    op.execute(
        """
        create or replace function app.is_verified_actor()
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select exists (
                select 1
                from public.perfiles p
                where p.id = (select app.current_actor_id())
                  and p.correo_verificado_en is not null
                  and p.eliminado_en is null
            );
        $$;
        """
    )
    op.execute(
        """
        create or replace function app.has_membership(p_conversacion_id uuid)
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select exists (
                select 1
                from public.miembros_conversacion m
                where m.conversacion_id = p_conversacion_id
                  and m.usuario_id = (select app.current_actor_id())
                  and (select app.is_verified_actor())
            );
        $$;
        """
    )
    op.execute(
        """
        create or replace function app.has_period(
            p_conversacion_id uuid,
            p_instante timestamptz
        )
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select exists (
                select 1
                from public.miembros_conversacion m
                where m.conversacion_id = p_conversacion_id
                  and m.usuario_id = (select app.current_actor_id())
                  and m.unido_en <= p_instante
                  and (m.salido_en is null or m.salido_en > p_instante)
                  and (select app.is_verified_actor())
            );
        $$;
        """
    )
    op.execute(
        """
        create or replace function app.is_active_member(p_conversacion_id uuid)
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select exists (
                select 1
                from public.miembros_conversacion m
                where m.conversacion_id = p_conversacion_id
                  and m.usuario_id = (select app.current_actor_id())
                  and m.salido_en is null
                  and m.estado = 'active'
                  and (select app.is_verified_actor())
            );
        $$;
        """
    )
    op.execute(
        """
        create or replace function app.is_active_admin(p_conversacion_id uuid)
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select exists (
                select 1
                from public.miembros_conversacion m
                where m.conversacion_id = p_conversacion_id
                  and m.usuario_id = (select app.current_actor_id())
                  and m.rol = 'admin'
                  and m.salido_en is null
                  and m.estado = 'active'
                  and (select app.is_verified_actor())
            );
        $$;
        """
    )
    op.execute(
        """
        create or replace function app.can_bootstrap_membership(
            p_conversacion_id uuid,
            p_usuario_id uuid
        )
        returns boolean
        language sql
        stable
        security definer
        set search_path = public, pg_temp
        as $$
            select (
                p_usuario_id = (select app.current_actor_id())
                and (select app.is_verified_actor())
                and exists (
                    select 1
                    from public.conversaciones c
                    where c.id = p_conversacion_id
                      and (
                          (
                              c.tipo = 'direct'
                              and p_usuario_id in (c.usuario_directo_menor, c.usuario_directo_mayor)
                              and (
                                  select count(*)
                                  from public.miembros_conversacion m
                                  where m.conversacion_id = c.id
                              ) < 2
                          )
                          or
                          (
                              c.tipo = 'group'
                              and p_usuario_id = c.creado_por
                              and not exists (
                                  select 1
                                  from public.miembros_conversacion m
                                  where m.conversacion_id = c.id
                              )
                          )
                      )
                )
            );
        $$;
        """
    )

    # 2) RLS activa en las seis tablas del chat.
    for table, _ in _TABLES:
        op.execute(f"alter table public.{table} enable row level security")

    for table, prefix in _TABLES:
        for suffix in _POLICY_SUFFIXES:
            op.execute(f"drop policy if exists {prefix}_{suffix} on public.{table}")

    # 2.1) conversaciones (§5.3)
    op.execute(
        """
        create policy conversaciones_select_realtime_activo on public.conversaciones
            for select to authenticated
            using ((select app.is_active_member(id)))
        """
    )
    op.execute(
        """
        create policy conversaciones_select_backend_membresia on public.conversaciones
            for select to chatly_app
            using ((select app.has_membership(id)))
        """
    )
    op.execute(
        """
        create policy conversaciones_insert_backend on public.conversaciones
            for insert to chatly_app
            with check (
                creado_por = (select app.current_actor_id())
                and (select app.is_verified_actor())
            )
        """
    )
    op.execute(
        """
        create policy conversaciones_update_admin on public.conversaciones
            for update to chatly_app
            using ((select app.is_active_admin(id)))
            with check ((select app.is_active_admin(id)))
        """
    )

    # 2.2) miembros_conversacion (§5.4)
    op.execute(
        """
        create policy miembros_select_realtime_activos on public.miembros_conversacion
            for select to authenticated
            using ((select app.is_active_member(conversacion_id)))
        """
    )
    op.execute(
        """
        create policy miembros_select_backend on public.miembros_conversacion
            for select to chatly_app
            using ((select app.has_membership(conversacion_id)))
        """
    )
    op.execute(
        """
        create policy miembros_insert_backend on public.miembros_conversacion
            for insert to chatly_app
            with check (
                exists (
                    select 1
                    from public.perfiles p
                    where p.id = usuario_id
                      and p.correo_verificado_en is not null
                      and p.eliminado_en is null
                )
                and (
                    (select app.is_active_admin(conversacion_id))
                    or (
                        usuario_id = (select app.current_actor_id())
                        and (select app.can_bootstrap_membership(conversacion_id, usuario_id))
                    )
                )
            )
        """
    )
    op.execute(
        """
        create policy miembros_update_backend on public.miembros_conversacion
            for update to chatly_app
            using (
                (select app.is_active_admin(conversacion_id))
                or usuario_id = (select app.current_actor_id())
            )
            with check (
                (select app.is_active_admin(conversacion_id))
                or usuario_id = (select app.current_actor_id())
            )
        """
    )

    # 2.3) preferencias_conversacion (§5.5)
    op.execute(
        """
        create policy preferencias_select_propio on public.preferencias_conversacion
            for select to chatly_app
            using (usuario_id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy preferencias_insert_propio on public.preferencias_conversacion
            for insert to chatly_app
            with check (usuario_id = (select app.current_actor_id()))
        """
    )
    op.execute(
        """
        create policy preferencias_update_propio on public.preferencias_conversacion
            for update to chatly_app
            using (usuario_id = (select app.current_actor_id()))
            with check (usuario_id = (select app.current_actor_id()))
        """
    )

    # 2.4) mensajes (§5.6): lectura limitada al periodo de membresía.
    op.execute(
        """
        create policy mensajes_select_por_periodo on public.mensajes
            for select to authenticated, chatly_app
            using ((select app.has_period(conversacion_id, creado_en)))
        """
    )
    op.execute(
        """
        create policy mensajes_insert_backend on public.mensajes
            for insert to chatly_app
            with check (
                (select app.is_active_member(conversacion_id))
                and (
                    (tipo in ('text','poll') and autor_id = (select app.current_actor_id()))
                    or tipo = 'system'
                )
            )
        """
    )
    op.execute(
        """
        create policy mensajes_update_propio on public.mensajes
            for update to chatly_app
            using (
                tipo = 'text'
                and autor_id = (select app.current_actor_id())
                and (select app.is_active_member(conversacion_id))
            )
            with check (
                tipo = 'text'
                and autor_id = (select app.current_actor_id())
                and (select app.is_active_member(conversacion_id))
            )
        """
    )

    # 2.5) versiones_mensaje (§5.7)
    op.execute(
        """
        create policy versiones_select_backend_autor on public.versiones_mensaje
            for select to chatly_app
            using (
                exists (
                    select 1
                    from public.mensajes m
                    where m.id = mensaje_id
                      and m.autor_id = (select app.current_actor_id())
                )
            )
        """
    )
    op.execute(
        """
        create policy versiones_insert_backend_autor on public.versiones_mensaje
            for insert to chatly_app
            with check (
                editado_por = (select app.current_actor_id())
                and exists (
                    select 1
                    from public.mensajes m
                    where m.id = mensaje_id
                      and m.autor_id = (select app.current_actor_id())
                      and (select app.is_active_member(m.conversacion_id))
                )
            )
        """
    )

    # 2.6) reacciones_mensaje (§5.8)
    op.execute(
        """
        create policy reacciones_select_por_periodo on public.reacciones_mensaje
            for select to authenticated, chatly_app
            using (
                exists (
                    select 1
                    from public.mensajes m
                    where m.id = mensaje_id
                      and m.eliminado_en is null
                      and (select app.has_period(m.conversacion_id, m.creado_en))
                )
            )
        """
    )
    op.execute(
        """
        create policy reacciones_insert_propia on public.reacciones_mensaje
            for insert to chatly_app
            with check (
                usuario_id = (select app.current_actor_id())
                and exists (
                    select 1
                    from public.mensajes m
                    where m.id = mensaje_id
                      and m.eliminado_en is null
                      and m.tipo in ('text','poll')
                      and (select app.is_active_member(m.conversacion_id))
                )
            )
        """
    )
    op.execute(
        """
        create policy reacciones_update_propia on public.reacciones_mensaje
            for update to chatly_app
            using (
                usuario_id = (select app.current_actor_id())
                and exists (
                    select 1
                    from public.mensajes m
                    where m.id = mensaje_id
                      and m.eliminado_en is null
                      and (select app.is_active_member(m.conversacion_id))
                )
            )
            with check (usuario_id = (select app.current_actor_id()))
        """
    )

    # 3) Ajustes obligatorios que RLS introduce en objetos ya existentes.
    #
    # `tocar_actividad_conversacion` (0004) actualiza `conversaciones` desde el
    # trigger de inserción de mensajes. Al activar RLS, esa actualización corre
    # como `chatly_app` y la única política de UPDATE es la del administrador,
    # así que en un chat directo el UPDATE afectaría cero filas y la lista de
    # conversaciones se ordenaría mal en silencio. Como el trigger solo mantiene
    # `ultimo_mensaje_en` y `actualizado_en`, se marca `SECURITY DEFINER`.
    op.execute(
        """
        create or replace function public.tocar_actividad_conversacion()
        returns trigger
        language plpgsql
        security definer
        set search_path = public, pg_temp
        as $$
        begin
            update public.conversaciones
               set ultimo_mensaje_en =
                       greatest(coalesce(ultimo_mensaje_en, new.creado_en), new.creado_en),
                   actualizado_en = now()
             where id = new.conversacion_id;
            return new;
        end $$;
        """
    )

    # La política de UPDATE permite al propio usuario tocar su fila de
    # membresía; sin esta guarda podría reabrir un periodo cerrado o cambiar
    # `usuario_id`. §5.4 exige el trigger.
    op.execute(
        """
        create or replace function public.proteger_periodo_membresia()
        returns trigger
        language plpgsql
        security definer
        set search_path = public, pg_temp
        as $$
        declare
            v_actor uuid := (select app.current_actor_id());
        begin
            if new.conversacion_id <> old.conversacion_id
               or new.usuario_id <> old.usuario_id
               or new.unido_en <> old.unido_en then
                raise exception 'No se puede cambiar la conversación, el usuario'
                    ' ni el inicio del periodo.'
                    using errcode = '42501';
            end if;

            if old.salido_en is not null then
                raise exception 'Un periodo de membresía cerrado no se reabre.'
                    using errcode = '42501';
            end if;

            -- Sin contexto de actor no hay política RLS que permita el UPDATE;
            -- se deja pasar para migraciones y semillas.
            if v_actor is null then
                return new;
            end if;

            if (select app.is_active_admin(old.conversacion_id)) then
                return new;
            end if;

            if old.usuario_id = v_actor
               and new.estado = 'left'
               and new.salido_en is not null
               and new.retirado_por is null
               and new.rol = old.rol then
                return new;
            end if;

            raise exception 'No tienes permiso para modificar esta membresía.'
                using errcode = '42501';
        end $$;
        """
    )
    op.execute(
        "drop trigger if exists trg_miembros_proteger_periodo on public.miembros_conversacion"
    )
    op.execute(
        """
        create trigger trg_miembros_proteger_periodo
            before update on public.miembros_conversacion
            for each row execute function public.proteger_periodo_membresia()
        """
    )

    # 4) Grants por tabla. Sin `DELETE`: los borrados del chat son lógicos.
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from pg_roles where rolname = 'chatly_app') then
            execute 'grant usage on schema app to chatly_app';
            execute 'grant execute on function app.is_verified_actor() to chatly_app';
            execute 'grant execute on function app.has_membership(uuid) to chatly_app';
            execute 'grant execute on function app.has_period(uuid, timestamptz) to chatly_app';
            execute 'grant execute on function app.is_active_member(uuid) to chatly_app';
            execute 'grant execute on function app.is_active_admin(uuid) to chatly_app';
            execute 'grant execute on function app.can_bootstrap_membership(uuid, uuid)'
                    ' to chatly_app';

            execute 'grant select, insert, update on public.conversaciones to chatly_app';
            execute 'grant select, insert, update on public.miembros_conversacion to chatly_app';
            execute 'grant select, insert, update on public.preferencias_conversacion'
                    ' to chatly_app';
            execute 'grant select, insert, update on public.mensajes to chatly_app';
            execute 'grant select, insert on public.versiones_mensaje to chatly_app';
            execute 'grant select, insert, update on public.reacciones_mensaje to chatly_app';
          end if;

          -- Realtime (0010) evalúa estas políticas como `authenticated`.
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'grant execute on function app.is_verified_actor() to authenticated';
            execute 'grant execute on function app.is_active_member(uuid) to authenticated';
            execute 'grant execute on function app.has_period(uuid, timestamptz)'
                    ' to authenticated';
          end if;

          if exists (select 1 from pg_roles where rolname = 'anon') then
            execute 'revoke all on public.conversaciones from anon';
            execute 'revoke all on public.miembros_conversacion from anon';
            execute 'revoke all on public.preferencias_conversacion from anon';
            execute 'revoke all on public.mensajes from anon';
            execute 'revoke all on public.versiones_mensaje from anon';
            execute 'revoke all on public.reacciones_mensaje from anon';
          end if;

          -- El navegador no consulta estas tablas: todo pasa por la API con
          -- `chatly_app`. Los grants a `authenticated` llegan en 0010_realtime.
          if exists (select 1 from pg_roles where rolname = 'authenticated') then
            execute 'revoke all on public.conversaciones from authenticated';
            execute 'revoke all on public.miembros_conversacion from authenticated';
            execute 'revoke all on public.preferencias_conversacion from authenticated';
            execute 'revoke all on public.mensajes from authenticated';
            execute 'revoke all on public.versiones_mensaje from authenticated';
            execute 'revoke all on public.reacciones_mensaje from authenticated';
          end if;
        end
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "drop trigger if exists trg_miembros_proteger_periodo on public.miembros_conversacion"
    )
    op.execute("drop function if exists public.proteger_periodo_membresia()")

    # Se restaura la versión sin `SECURITY DEFINER` de 0004.
    op.execute(
        """
        create or replace function public.tocar_actividad_conversacion()
        returns trigger language plpgsql as $$
        begin
            update public.conversaciones
               set ultimo_mensaje_en =
                       greatest(coalesce(ultimo_mensaje_en, new.creado_en), new.creado_en),
                   actualizado_en = now()
             where id = new.conversacion_id;
            return new;
        end $$;
        """
    )

    for table, prefix in _TABLES:
        for suffix in _POLICY_SUFFIXES:
            op.execute(f"drop policy if exists {prefix}_{suffix} on public.{table}")
        op.execute(f"alter table public.{table} disable row level security")

    for function in _FUNCTIONS:
        op.execute(f"drop function if exists {function}")
