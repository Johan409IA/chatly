# Chatly — Matriz de autorización

> **Estado:** propuesta para revisión del equipo.
> **Base:** `docs/chatly.md` (Q1–Q112), `docs/database-schema.md` y `docs/architecture.md`.
> **Principio:** dos barreras independientes. El servicio valida reglas de dominio; RLS vuelve a validar fila por fila. Ninguna operación confía en un `user_id` enviado por el cliente.

---

## 1. Sujetos y roles

| Sujeto | Rol PostgreSQL | Identidad | Acceso |
|---|---|---|---|
| Visitante | `anon` | ninguna | Solo `/api/health`, registro y login |
| Usuario autenticado | `authenticated` | JWT de Supabase Auth | Lectura acotada por RLS; escrituras solo a través de la API |
| Backend | `chatly_app` | `app.current_user_id` por transacción | Lectura/escritura según reglas; nunca `BYPASSRLS` |
| Migraciones / semilla | propietario de tablas | — | DDL y datos de demostración |
| Realtime | `authenticated` con claims | JWT del suscriptor | Políticas de `realtime.messages` + RLS de tablas |

**Reglas transversales**

- El navegador **no** escribe tablas de negocio. Toda escritura pasa por FastAPI/servicios.
- El navegador solo recibe tablas por Realtime (lectura) y Storage (avatares).
- `service_role` no se usa en el flujo normal.
- `user_metadata` **nunca** se usa para autorizar: es editable por el usuario. Los datos de autorización viven en `profiles` (rol y verificación).

---

## 2. Estados de un actor respecto a una conversación

| Estado | Condición | Puede leer | Puede escribir |
|---|---|---|---|
| Miembro activo | `joined_at <= now() and left_at is null` | Mensajes de sus periodos | Sí, según su rol |
| Antiguo miembro | Tiene al menos un periodo cerrado | Solo mensajes de sus periodos | No |
| Expulsado | Periodo cerrado con `status='removed'` | Solo mensajes de sus periodos | No |
| Reincorporado | Varios periodos; el último activo | Periodos anteriores + actual, nunca el intervalo ausente | Sí |
| Ajeno | Sin periodos | Nada | Nada |
| No verificado | `profiles.email_verified_at is null` | Nada de chat | Nada de chat (Q15) |

---

## 3. Funciones auxiliares

Todas viven en el esquema no expuesto `app` y son `stable`. Las cinco funciones de membresía son **`security definer`** por una razón concreta: consultan `conversation_memberships` y, si se ejecutaran como invocador, la política de esa tabla las volvería a llamar y produciría recursión de RLS. La sección 3.1 explica las precauciones.

```sql
create schema if not exists app;

-- Identidad: sirve tanto a Realtime/PostgREST (auth.uid()) como a la conexión directa.
create or replace function app.current_actor_id() returns uuid
language sql stable
set search_path = public, pg_temp
as $$
    select coalesce(
        auth.uid(),
        nullif(current_setting('app.current_user_id', true), '')::uuid
    );
$$;

-- ¿El actor tiene algún periodo (activo o cerrado) en la conversación?
create or replace function app.has_membership(p_conversation_id uuid)
returns boolean
language sql stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.conversation_memberships m
        where m.conversation_id = p_conversation_id
          and m.user_id = (select app.current_actor_id())
    );
$$;

-- ¿El actor pertenecía en el instante p_at?
create or replace function app.has_period(p_conversation_id uuid, p_at timestamptz)
returns boolean
language sql stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.conversation_memberships m
        where m.conversation_id = p_conversation_id
          and m.user_id = (select app.current_actor_id())
          and m.joined_at <= p_at
          and (m.left_at is null or m.left_at > p_at)
    );
$$;

-- ¿Es miembro activo ahora?
create or replace function app.is_active_member(p_conversation_id uuid)
returns boolean
language sql stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.conversation_memberships m
        where m.conversation_id = p_conversation_id
          and m.user_id = (select app.current_actor_id())
          and m.left_at is null
    );
$$;

-- ¿Es el administrador activo?
create or replace function app.is_active_admin(p_conversation_id uuid)
returns boolean
language sql stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.conversation_memberships m
        where m.conversation_id = p_conversation_id
          and m.user_id = (select app.current_actor_id())
          and m.role = 'admin'
          and m.left_at is null
    );
$$;

-- ¿Puede este usuario crear la primera membresía de una conversación recién creada?
-- Evita que RLS oculte las membresías existentes y permita una autoinserción indebida.
create or replace function app.can_bootstrap_membership(
    p_conversation_id uuid,
    p_user_id uuid
) returns boolean
language sql stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.conversations c
        where c.id = p_conversation_id
          and (
              (c.type = 'direct'
               and p_user_id in (c.direct_user_low, c.direct_user_high)
               and (select count(*) from public.conversation_memberships m
                    where m.conversation_id = c.id) < 2)
              or
              (c.type = 'group'
               and p_user_id = c.created_by
               and not exists (select 1 from public.conversation_memberships m
                               where m.conversation_id = c.id))
          )
    );
$$;

-- Parseo seguro del topic de Realtime: "conversation:<uuid>"
create or replace function app.topic_conversation_id() returns uuid
language sql stable
as $$
    select case
        when realtime.topic() ~ '^conversation:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        then split_part(realtime.topic(), ':', 2)::uuid
    end;
$$;

revoke all on function app.current_actor_id() from public;
revoke all on function app.has_membership(uuid) from public;
revoke all on function app.has_period(uuid, timestamptz) from public;
revoke all on function app.is_active_member(uuid) from public;
revoke all on function app.is_active_admin(uuid) from public;
revoke all on function app.can_bootstrap_membership(uuid, uuid) from public;
revoke all on function app.topic_conversation_id() from public;

grant execute on function app.current_actor_id() to authenticated, chatly_app;
grant execute on function app.has_membership(uuid) to authenticated, chatly_app;
grant execute on function app.has_period(uuid, timestamptz) to authenticated, chatly_app;
grant execute on function app.is_active_member(uuid) to authenticated, chatly_app;
grant execute on function app.is_active_admin(uuid) to authenticated, chatly_app;
grant execute on function app.can_bootstrap_membership(uuid, uuid) to authenticated, chatly_app;
grant execute on function app.topic_conversation_id() to authenticated;
```

**Por qué `(select app.current_actor_id())`:** envuelto en un subselect, PostgreSQL lo evalúa una vez por sentencia en lugar de una vez por fila. Es la práctica recomendada por Supabase para políticas con RLS.

### 3.1 Precauciones con `SECURITY DEFINER`

Las cinco funciones de membresía son `security definer` únicamente para romper la recursión de RLS y para resolver la creación inicial de una conversación. Se aplican todas las precauciones de Supabase:

- Viven en el esquema **no expuesto** `app`, no en `public`.
- `search_path` fijado a `public, pg_temp`; no hay SQL dinámico.
- `EXECUTE` revocado de `PUBLIC` y concedido solo a `authenticated` y `chatly_app`.
- Retornan solo `boolean`; filtran por `app.current_actor_id()` y, si no hay actor, no encuentran filas y devuelven `false`.
- No revelan datos ni permiten elegir columnas.
- Se ejecutará `supabase db advisors` después de crearlas para confirmar que no hay hallazgos.

Alternativa descartada: denormalizar la membresía en el JWT. No sirve porque la visibilidad depende de periodos históricos y de mensajes anteriores a la entrada o posteriores a la salida.

---

## 4. Matriz funcional

Leyenda: **Sí** = permitido con sus reglas; **No** = denegado; **Período** = solo filas dentro de sus periodos de membresía; **Propio** = solo sus filas.

| Operación | Activo | Antiguo/expulsado | Ajeno | No verificado |
|---|---|---|---|---|
| Ver lista de conversaciones | Sí | Sí (solo lectura) | No | No |
| Leer historial | Período | Período | No | No |
| Enviar mensaje | Sí | No | No | No |
| Responder mensaje | Sí | No | No | No |
| Editar/eliminar mensaje propio | Sí | No | No | No |
| Reaccionar | Sí | No | No | No |
| Crear encuesta | Sí | No | No | No |
| Editar encuesta propia (sin votos) | Sí | No | No | No |
| Cerrar encuesta | Creador; admin si el creador ya no está | No | No | No |
| Votar / cambiar voto | Sí, encuesta abierta | No | No | No |
| Ocultar conversación | Propio | Propio | No | No |
| Salir del grupo | Sí | No | No | No |
| Añadir/expulsar integrantes | Solo admin activo | No | No | No |
| Renombrar grupo | Solo admin activo | No | No | No |
| Buscar usuarios | Sí | Sí | Sí | No |
| Ver perfil ajeno | Sí (edad, género, nombre, alias, foto) | Sí | Sí | No |
| Ver perfil propio completo | Sí | Sí | — | Sí |
| Editar perfil propio | Sí | Sí | No | Sí |
| Leer auditoría | No | No | No | No |

---

## 5. Políticas RLS por tabla

Todas las tablas tienen `enable row level security`. Las escrituras se conceden **solo** a `chatly_app`; `authenticated` únicamente lee lo que Realtime necesita.

### 5.1 `profiles`

```sql
alter table public.profiles enable row level security;

create policy profiles_select_backend on public.profiles
    for select to chatly_app
    using ((select app.current_actor_id()) is not null);

create policy profiles_insert_self on public.profiles
    for insert to chatly_app
    with check (id = (select app.current_actor_id()));

create policy profiles_update_self on public.profiles
    for update to chatly_app
    using (id = (select app.current_actor_id()))
    with check (id = (select app.current_actor_id()));
```

- El navegador no tiene `select` sobre esta tabla: los perfiles se sirven por la API.
- `birth_date` solo se devuelve en el perfil propio (Q109).
- No hay política de `delete` (Q42).

### 5.2 `user_contacts`

```sql
alter table public.user_contacts enable row level security;

create policy user_contacts_insert_backend on public.user_contacts
    for insert to chatly_app
    with check (user_id = (select app.current_actor_id()));

create policy user_contacts_update_backend on public.user_contacts
    for update to chatly_app
    using (user_id = (select app.current_actor_id()))
    with check (user_id = (select app.current_actor_id()));
```

- Sin política de `select`: nadie lee la tabla directamente.
- La búsqueda exacta por correo pasa por `app.find_user_by_email` (Q73).

### 5.3 `conversations`

```sql
alter table public.conversations enable row level security;

create policy conversations_select on public.conversations
    for select to authenticated, chatly_app
    using ((select app.has_membership(id)));

create policy conversations_insert_backend on public.conversations
    for insert to chatly_app
    with check (created_by = (select app.current_actor_id()));

create policy conversations_update_admin on public.conversations
    for update to chatly_app
    using ((select app.is_active_admin(id)))
    with check ((select app.is_active_admin(id)));
```

- Un antiguo miembro sigue viendo la conversación para consultar su historial (Q21, Q90).
- El archivo se ejecuta **antes** de cerrar la última membresía, para que el actor siga siendo admin activo en la evaluación de la política.

### 5.4 `conversation_memberships`

```sql
alter table public.conversation_memberships enable row level security;

create policy memberships_select on public.conversation_memberships
    for select to authenticated, chatly_app
    using ((select app.has_membership(conversation_id)));

create policy memberships_insert on public.conversation_memberships
    for insert to chatly_app
    with check (
        (select app.is_active_admin(conversation_id))
        or (
            user_id = (select app.current_actor_id())
            and (select app.can_bootstrap_membership(conversation_id, user_id))
        )
    );

create policy memberships_update on public.conversation_memberships
    for update to chatly_app
    using (
        (select app.is_active_admin(conversation_id))
        or user_id = (select app.current_actor_id())
    )
    with check (
        (select app.is_active_admin(conversation_id))
        or user_id = (select app.current_actor_id())
    );
```

**Trigger de protección** (además de RLS, para que un error del servicio no escale privilegios):

```sql
create or replace function app.guard_membership_update()
returns trigger language plpgsql as $$
begin
    if new.conversation_id <> old.conversation_id
       or new.user_id <> old.user_id
       or new.joined_at <> old.joined_at
       or new.added_by is distinct from old.added_by then
        raise exception 'No se pueden alterar los datos de identidad de la membresía'
            using errcode = '42501';
    end if;

    if new.role <> old.role and not app.is_active_admin(old.conversation_id) then
        raise exception 'Solo el administrador activo puede cambiar roles'
            using errcode = '42501';
    end if;

    if old.left_at is not null and new.left_at is null then
        raise exception 'Una membresía cerrada no se reactiva; se crea un periodo nuevo'
            using errcode = '42501';
    end if;
    return new;
end $$;
```

- La primera membresía se crea con `app.can_bootstrap_membership`. En grupos, el creador se inserta con `role = 'admin'`; en conversaciones directas también queda como admin para poder insertar al segundo participante. Si la primera membresía de un grupo no fuera admin, nadie podría añadir al resto.
- `can_bootstrap_membership` es `security definer` porque, ejecutada como invocador, RLS ocultaría las membresías existentes y permitiría que cualquier usuario se autoinsertara en un grupo ajeno.
- El periodo se cierra con `left_at` y `status`; no se borra (Q58).
- Reincorporarse crea una fila nueva (Q36, Q98).
- Límite de 10 integrantes: se valida en el servicio con `SELECT ... FOR UPDATE` sobre la conversación (Q8).

### 5.5 `conversation_user_preferences`

```sql
alter table public.conversation_user_preferences enable row level security;

create policy prefs_select on public.conversation_user_preferences
    for select to chatly_app
    using (user_id = (select app.current_actor_id()));

create policy prefs_insert on public.conversation_user_preferences
    for insert to chatly_app
    with check (user_id = (select app.current_actor_id()));

create policy prefs_update on public.conversation_user_preferences
    for update to chatly_app
    using (user_id = (select app.current_actor_id()))
    with check (user_id = (select app.current_actor_id()));
```

- La preferencia es individual (Q68) y no impide volver a abrir el chat (Q105).

### 5.6 `messages`

```sql
alter table public.messages enable row level security;

create policy messages_select on public.messages
    for select to authenticated, chatly_app
    using ((select app.has_period(conversation_id, created_at)));

create policy messages_insert on public.messages
    for insert to chatly_app
    with check (
        (select app.is_active_member(conversation_id))
        and (
            (type in ('text','poll') and author_id = (select app.current_actor_id()))
            or type = 'system'
        )
    );

create policy messages_update_own on public.messages
    for update to chatly_app
    using (
        type = 'text'
        and author_id = (select app.current_actor_id())
        and (select app.is_active_member(conversation_id))
    )
    with check (
        type = 'text'
        and author_id = (select app.current_actor_id())
        and (select app.is_active_member(conversation_id))
    );
```

- La lectura se resuelve por periodo: un reincorporado no ve el intervalo ausente (Q36, Q96, Q104).
- El borrado es un `UPDATE` de `deleted_at`; no hay `DELETE` (Q85).
- Los mensajes de sistema los inserta el servicio con `author_id = null` (Q100).

### 5.7 `message_versions`

```sql
alter table public.message_versions enable row level security;

create policy versions_select_backend on public.message_versions
    for select to chatly_app
    using (
        exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.author_id = (select app.current_actor_id())
        )
    );

create policy versions_insert_backend on public.message_versions
    for insert to chatly_app
    with check (
        edited_by = (select app.current_actor_id())
        and exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.author_id = (select app.current_actor_id())
        )
    );
```

- Solo backend; no hay interfaz de consulta en V1 (Q33).

### 5.8 `message_reactions`

```sql
alter table public.message_reactions enable row level security;

create policy reactions_select on public.message_reactions
    for select to authenticated, chatly_app
    using (
        exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.deleted_at is null
              and (select app.has_period(m.conversation_id, m.created_at))
        )
    );

create policy reactions_insert on public.message_reactions
    for insert to chatly_app
    with check (
        user_id = (select app.current_actor_id())
        and exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.deleted_at is null
              and m.type in ('text','poll')
              and (select app.is_active_member(m.conversation_id))
        )
    );

create policy reactions_update on public.message_reactions
    for update to chatly_app
    using (
        user_id = (select app.current_actor_id())
        and exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.deleted_at is null
              and (select app.is_active_member(m.conversation_id))
        )
    )
    with check (
        user_id = (select app.current_actor_id())
        and exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.deleted_at is null
              and (select app.is_active_member(m.conversation_id))
        )
    );
```

- Una reacción vigente por usuario y mensaje (Q12, Q70).
- Un antiguo integrante no puede reaccionar (Q104).

### 5.9 `polls`

```sql
alter table public.polls enable row level security;

create policy polls_select on public.polls
    for select to authenticated, chatly_app
    using (
        exists (
            select 1 from public.messages m
            where m.id = message_id
              and (select app.has_period(m.conversation_id, m.created_at))
        )
    );

create policy polls_insert on public.polls
    for insert to chatly_app
    with check (
        created_by = (select app.current_actor_id())
        and (select app.is_active_member(conversation_id))
        and exists (
            select 1 from public.messages m
            where m.id = message_id
              and m.type = 'poll'
              and m.author_id = (select app.current_actor_id())
        )
    );

create policy polls_update on public.polls
    for update to chatly_app
    using (
        (select app.is_active_member(conversation_id))
        and (
            created_by = (select app.current_actor_id())
            or (select app.is_active_admin(conversation_id))
        )
    )
    with check (
        (select app.is_active_member(conversation_id))
        and (
            created_by = (select app.current_actor_id())
            or (select app.is_active_admin(conversation_id))
        )
    );
```

- RLS habilita al creador o al admin; el servicio aplica las reglas finas: solo el creador edita y solo antes del primer voto (Q88, Q92); el admin solo puede cerrar (Q24, Q108).

### 5.10 `poll_options`

```sql
alter table public.poll_options enable row level security;

create policy options_select on public.poll_options
    for select to authenticated, chatly_app
    using (
        exists (
            select 1
            from public.polls p
            join public.messages m on m.id = p.message_id
            where p.id = poll_id
              and (select app.has_period(m.conversation_id, m.created_at))
        )
    );

create policy options_insert on public.poll_options
    for insert to chatly_app
    with check (
        exists (
            select 1 from public.polls p
            where p.id = poll_id
              and p.created_by = (select app.current_actor_id())
              and (select app.is_active_member(p.conversation_id))
        )
    );

create policy options_update_before_votes on public.poll_options
    for update to chatly_app
    using (
        exists (
            select 1 from public.polls p
            where p.id = poll_id
              and p.created_by = (select app.current_actor_id())
              and (select app.is_active_member(p.conversation_id))
              and not exists (select 1 from public.poll_votes v where v.poll_id = p.id)
        )
    )
    with check (
        exists (
            select 1 from public.polls p
            where p.id = poll_id
              and p.created_by = (select app.current_actor_id())
              and (select app.is_active_member(p.conversation_id))
              and not exists (select 1 from public.poll_votes v where v.poll_id = p.id)
        )
    );
```

- Las opciones quedan bloqueadas tras el primer voto (Q88).

### 5.11 `poll_votes`

```sql
alter table public.poll_votes enable row level security;

create policy votes_select on public.poll_votes
    for select to authenticated, chatly_app
    using (
        exists (
            select 1
            from public.polls p
            join public.messages m on m.id = p.message_id
            where p.id = poll_id
              and (select app.has_period(m.conversation_id, m.created_at))
        )
    );

create policy votes_insert on public.poll_votes
    for insert to chatly_app
    with check (
        user_id = (select app.current_actor_id())
        and exists (
            select 1 from public.polls p
            where p.id = poll_id
              and p.status = 'open'
              and (select app.is_active_member(p.conversation_id))
        )
    );

create policy votes_update on public.poll_votes
    for update to chatly_app
    using (
        user_id = (select app.current_actor_id())
        and exists (
            select 1 from public.polls p
            where p.id = poll_id
              and p.status = 'open'
              and (select app.is_active_member(p.conversation_id))
        )
    )
    with check (
        user_id = (select app.current_actor_id())
        and exists (
            select 1 from public.polls p
            where p.id = poll_id
              and p.status = 'open'
              and (select app.is_active_member(p.conversation_id))
        )
    );
```

- Un voto vigente por usuario y encuesta (Q69).
- Cambiar el voto es un `UPDATE` de `option_id`.
- Los votos históricos se conservan aunque el usuario salga (Q49).

### 5.12 `audit_logs`

```sql
alter table public.audit_logs enable row level security;

create policy audit_insert_backend on public.audit_logs
    for insert to chatly_app
    with check (
        actor_id is null or actor_id = (select app.current_actor_id())
    );
```

- Sin políticas de `select`, `update` ni `delete`: ni el navegador ni el backend leen la auditoría por la aplicación (Q32).
- Las herramientas administrativas usan el rol propietario fuera de la app.

---

## 6. Autorización de Realtime

### 6.1 Canales privados

Un único canal por conversación: `conversation:<uuid>`, con `private: true`. En él conviven Postgres Changes, Presence y Broadcast.

```sql
-- RLS de realtime.messages ya está habilitado. NO ejecutar ALTER TABLE ... ENABLE RLS.
create policy realtime_channel_read on realtime.messages
    for select to authenticated
    using (
        realtime.messages.extension in ('broadcast','presence')
        and (select app.is_active_member(app.topic_conversation_id()))
    );

create policy realtime_channel_write on realtime.messages
    for insert to authenticated
    with check (
        realtime.messages.extension in ('broadcast','presence')
        and (select app.is_active_member(app.topic_conversation_id()))
    );
```

- Un antiguo miembro no puede seguir en el canal: `is_active_member` es falso.
- Las políticas se evalúan al conectar y se cachean por la duración de la conexión. La revocación se aplica al renovar el JWT o al expirar (Q61).
- Postgres Changes usa las políticas de las tablas fuente; Realtime filtra filas por suscriptor.

### 6.2 Tablas publicadas

```sql
alter publication supabase_realtime add table
    public.conversations,
    public.conversation_memberships,
    public.messages,
    public.message_reactions,
    public.polls,
    public.poll_options,
    public.poll_votes;
```

- No se publican `profiles`, `user_contacts`, `message_versions` ni `audit_logs`.
- Los borrados son lógicos (`UPDATE`), así que no se depende de eventos `DELETE`.
- Si en el futuro se necesitan registros `old`, se configurará `replica identity full` en la tabla correspondiente.

---

## 7. Storage (avatares)

- Bucket privado `avatars` (Q102).
- Límites del bucket: `file_size_limit = 2097152` (2 MB) y `allowed_mime_types = {'image/jpeg','image/png','image/webp'}` (Q18).
- Ruta obligatoria: `{user_id}/{uuid}.{ext}`.

```sql
create policy avatars_read on storage.objects
    for select to authenticated
    using (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

create policy avatars_insert on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'avatars'
        and owner_id = (select auth.uid())
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

-- Upsert exige SELECT + INSERT + UPDATE
create policy avatars_update on storage.objects
    for update to authenticated
    using (
        bucket_id = 'avatars'
        and owner_id = (select auth.uid())
        and (storage.foldername(name))[1] = (select auth.uid())::text
    )
    with check (
        bucket_id = 'avatars'
        and owner_id = (select auth.uid())
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

create policy avatars_delete on storage.objects
    for delete to authenticated
    using (
        bucket_id = 'avatars'
        and owner_id = (select auth.uid())
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );
```

- La subida es directa con `supabase-js`; el backend después verifica el objeto (`HEAD`: tamaño y `content-type`) antes de actualizar `profiles.avatar_path`.
- La visualización usa URLs firmadas de duración corta generadas por el backend.
- Un usuario no puede escribir ni leer la carpeta de otro.

---

## 8. Grants

```sql
-- El navegador no toca tablas de negocio salvo lectura para Realtime.
revoke all on all tables in schema public from anon, authenticated;

grant select on public.conversations,
                public.conversation_memberships,
                public.messages,
                public.message_reactions,
                public.polls,
                public.poll_options,
                public.poll_votes
    to authenticated;

-- Backend: privilegios mínimos, sin DELETE y sin SELECT en auditoría ni user_contacts.
-- Se concede INSERT/SELECT a nivel de tabla y UPDATE solo por columnas.
grant select, insert on public.profiles to chatly_app;
grant insert on public.user_contacts to chatly_app;
grant select, insert on public.conversations to chatly_app;
grant select, insert on public.conversation_memberships to chatly_app;
grant select, insert on public.conversation_user_preferences to chatly_app;
grant select, insert on public.messages to chatly_app;
grant select, insert on public.message_versions to chatly_app;
grant select, insert on public.message_reactions to chatly_app;
grant select, insert on public.polls to chatly_app;
grant select, insert on public.poll_options to chatly_app;
grant select, insert on public.poll_votes to chatly_app;
grant insert on public.audit_logs to chatly_app;
grant usage, select on sequence public.audit_logs_id_seq to chatly_app;

-- Esquema no expuesto: solo backend y ejecución de funciones.
grant usage on schema app to chatly_app;
grant select on app.profiles_public to chatly_app;
grant execute on function app.find_user_by_email(text) to chatly_app;

-- Columnas actualizables: impiden cambiar autoría, identidad o fechas clave.
grant update (alias, display_name, avatar_path, birth_date, gender,
              email_verified_at, alias_changed_at, deleted_at, updated_at)
    on public.profiles to chatly_app;

grant update (email_normalized, updated_at) on public.user_contacts to chatly_app;

grant update (name, admin_id, is_archived, archived_at, last_message_at, updated_at)
    on public.conversations to chatly_app;

grant update (role, status, left_at, removed_by, last_read_message_id, last_read_at, updated_at)
    on public.conversation_memberships to chatly_app;

grant update (content, edited_at, edit_count, deleted_at, deleted_by, updated_at)
    on public.messages to chatly_app;

grant update (emoji, deleted_at, updated_at) on public.message_reactions to chatly_app;

grant update (question, status, closed_at, closed_by, deleted_at, updated_at)
    on public.polls to chatly_app;

grant update (text, position) on public.poll_options to chatly_app;

grant update (option_id, updated_at) on public.poll_votes to chatly_app;

grant update (hidden, hidden_at, updated_at)
    on public.conversation_user_preferences to chatly_app;
```

Notas:

- `anon` no recibe ningún privilegio de tabla.
- `chatly_app` no tiene `BYPASSRLS` ni es propietario de las tablas.
- No se concede `DELETE` en ninguna tabla de negocio.
- El propietario de las tablas (rol de migraciones) ejecuta la semilla y las tareas administrativas.

---

## 9. Casos negativos obligatorios (pruebas)

1. Usuario A intenta leer la conversación y los mensajes de B: 0 filas.
2. Antiguo miembro intenta leer mensajes posteriores a `left_at`: 0 filas.
3. Reincorporado intenta leer el intervalo en que estuvo fuera: 0 filas.
4. Integrante no admin intenta añadir o expulsar: 0 filas / error.
5. Admin intenta superar los 10 integrantes: rechazo del servicio.
6. Usuario intenta editar o eliminar un mensaje ajeno: 0 filas.
7. Usuario expulsado intenta reaccionar o votar: 0 filas.
8. Usuario intenta votar dos veces: violación de `uq_poll_votes_user`.
9. Usuario intenta votar en una encuesta cerrada: rechazo del servicio y de RLS.
10. Usuario intenta leer `user_contacts` directamente: permiso denegado.
11. Búsqueda por correo devuelve nombre, alias y foto, nunca el correo.
12. Suscripción a `conversation:<uuid>` ajena: rechazo de Realtime.
13. Subida o lectura de un avatar en la carpeta de otro: rechazo de Storage.
14. Intento de leer, editar o borrar `audit_logs` desde la app: permiso denegado.
15. Dos transacciones consecutivas con usuarios distintos no comparten `app.current_user_id`.
16. Un usuario no verificado no obtiene filas de chat aunque tenga JWT válido.

---

## 10. Límites de RLS y reglas que quedan en el servicio

RLS no puede expresar por sí sola:

- El máximo de 10 integrantes ni el mínimo de 3 al crear (requieren contar filas y bloquear la conversación).
- El límite de un cambio de alias cada 30 días.
- Que las opciones de una encuesta solo se editen antes del primer voto (se refuerza con RLS, pero la decisión final es del servicio).
- Que el cierre de encuesta por parte del admin solo ocurra cuando el creador ya no pertenece al grupo.
- La idempotencia de mensajes offline (`client_message_id`).
- La validez de la transición de estados de una encuesta o membresía.

Estas reglas viven en `backend/services/` y se prueban de forma negativa. RLS actúa como red de seguridad, no como sustituto.

---

## 11. Notas de rendimiento

- Índice `ix_memberships_policy_lookup (conversation_id, user_id, joined_at) include (left_at)` para `has_period`.
- Índice `ix_messages_conversation_cursor (conversation_id, created_at desc, id desc)` para lectura y Realtime.
- Las funciones auxiliares son `stable` y usan `(select ...)` para evaluarse una vez por sentencia.
- Realtime cachea las políticas por conexión; mantener las políticas simples reduce la latencia de `subscribe`.
- No se usan subconsultas `OR` costosas en políticas de tablas de alto volumen (`messages`); se apoya en los índices anteriores.
