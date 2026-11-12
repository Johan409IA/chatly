# Chatly — Matriz de autorización

> **Estado:** aprobado para implementación; las políticas y grants deben aplicarse en migraciones y validarse con pruebas negativas.  
> **Base funcional:** `docs/chatly.md` (Q1–Q179).  
> **Documentos técnicos relacionados:** `docs/database-schema.md`, `docs/api-contracts.md`, `docs/realtime-events.md` y `docs/architecture.md`.  
> **Modelo de persistencia:** Supabase PostgreSQL con nombres de tablas y columnas en español.  
> **Principio:** el servicio valida las reglas de dominio y PostgreSQL RLS vuelve a restringir el acceso a las filas. La identidad del actor se deriva de la sesión/JWT o del contexto transaccional del backend, nunca de un identificador enviado libremente por el cliente.

Este documento amplía la matriz original para contemplar perfiles públicos, intereses, grupos descubribles, solicitudes de unión, presencia por usuario y notificaciones sociales. No incorpora amistades, seguidores, solicitudes de contacto, bloqueo ni moderación.

> **Importante:** las políticas SQL de este documento son una propuesta de diseño. Antes de aplicarlas en Supabase deben contrastarse con las migraciones definitivas, los grants reales y pruebas negativas con los roles `authenticated` y `chatly_app`.

---

## 1. Sujetos, roles e identidad

| Sujeto | Rol PostgreSQL / contexto | Identidad | Acceso |
|---|---|---|---|
| Visitante | `anon` | Ninguna | `/api/health`, registro, login, confirmación y recuperación. Sin lectura de tablas de negocio. |
| Usuario autenticado no verificado | `authenticated` en Realtime/Storage; `chatly_app` en API | JWT válido, pero `perfiles.correo_verificado_en IS NULL` | Puede gestionar su perfil propio y completar el registro. No puede utilizar chats ni Descubrir. |
| Usuario autenticado y verificado | `authenticated` en Realtime/Storage; `chatly_app` en API | JWT válido y correo confirmado | Puede utilizar chats, búsquedas, Descubrir, perfiles e intereses según visibilidad y reglas de cada recurso. |
| Backend | `chatly_app` | `app.current_actor_id()` establecido por transacción | Acceso de negocio sujeto a RLS y a las reglas de servicio. Nunca tiene `BYPASSRLS` ni es propietario de las tablas. |
| Job de expiración | `pg_cron` ejecutado como `chatly_app` | Sin suplantar a un usuario; `resuelta_por = NULL` | Solo puede expirar solicitudes cuyo vencimiento ya ocurrió. No tiene permisos generales de administración. |
| Migraciones y semillas | Rol propietario/administrativo controlado | Credenciales de despliegue | DDL, políticas, catálogo inicial de intereses y datos demo. No se utiliza en las peticiones normales. |
| Realtime | `authenticated` con claims del JWT | `auth.uid()` | Acceso a topics privados mediante RLS de `realtime.messages`; Postgres Changes queda además limitado por RLS de las tablas fuente. |
| Publicador Realtime del servidor | Función SQL `app.publish_social_event(...)` | `SECURITY DEFINER` propiedad del rol de migraciones | Publica Broadcast privados de notificación e invalidación con `EXECUTE` solo a `chatly_app`. No se usa una credencial secreta en el backend. |

### Reglas transversales

1. El navegador no escribe tablas de negocio. Toda mutación de perfiles, intereses, conversaciones, membresías, mensajes, encuestas y solicitudes pasa por FastAPI/servicios.
2. Las excepciones de escritura directa son las operaciones de Storage del avatar propio, restringidas por bucket, propietario y ruta.
3. El navegador utiliza Supabase JS para suscribirse a Realtime. No consulta directamente las tablas sociales ni las tablas privadas del perfil.
4. `service_role` o cualquier clave secreta equivalente nunca se usa en el navegador. Los Broadcast sociales se publican con `app.publish_social_event(...)`; no se necesita una clave de publicador en el backend y la función no sustituye las validaciones de dominio.
5. `user_metadata` no se utiliza para autorizar. La verificación del correo se consulta desde `perfiles.correo_verificado_en`, sincronizado con Supabase Auth.
6. Las rutas REST responden `404` cuando un recurso no existe o no es visible para el actor, siguiendo el contrato de API.
7. Un grupo descubrible sigue siendo una fila de `conversaciones` con `tipo = 'group'`. No se crea una entidad separada de comunidad.
8. El job de `pg_cron` ejecuta únicamente `app.expire_pending_join_requests()`. El wrapper `app.publish_social_event` solo acepta eventos de la lista blanca y un destinatario válido; no acepta topics arbitrarios.

---

## 2. Estados de un actor respecto a perfiles, grupos y conversaciones

### 2.1 Estado de verificación

| Estado | Condición | Chats | Descubrir |
|---|---|---|---|
| No verificado | `perfiles.correo_verificado_en IS NULL` | No puede leer ni escribir chats | No puede consultar personas ni grupos descubribles |
| Verificado | `perfiles.correo_verificado_en IS NOT NULL` y perfil no eliminado | Según membresía | Puede utilizar personas, grupos y solicitudes según las reglas siguientes |

### 2.2 Estado de un actor respecto a una conversación

| Estado | Condición | Puede leer | Puede escribir |
|---|---|---|---|
| Miembro activo | `unido_en <= now()` y `salido_en IS NULL` | Mensajes de su periodo activo y periodos anteriores propios | Sí, según su rol y las reglas de cada recurso |
| Antiguo miembro | Tiene uno o más periodos cerrados | Solo mensajes cuyo `creado_en` cae dentro de uno de sus periodos | No |
| Expulsado | Periodo cerrado con `estado = 'removed'` | Solo mensajes de sus periodos anteriores | No |
| Reincorporado | Tiene varios periodos y uno activo | Periodos anteriores + actual; nunca el intervalo ausente | Sí durante el periodo activo |
| Ajeno | No tiene periodos de membresía | Nada del contenido de la conversación | Nada |
| Solicitante de grupo | Tiene una solicitud pendiente para un grupo descubrible | Información pública del grupo y su propia solicitud pendiente | No puede editar/cancelar la solicitud; puede esperar resolución o caducidad |

### 2.3 Visibilidad de personas

| Configuración | Recomendaciones | Búsqueda directa | Intereses visibles en perfil |
|---|---|---|---|
| `visibilidad_publica = true` | Puede aparecer si tiene al menos un interés y cumple los demás filtros | Sí | Sí, para usuarios verificados |
| `visibilidad_publica = false` | No aparece | Sí, por alias o correo exacto | No; se mantienen nombre, alias y fotografía en la búsqueda directa |
| Sin intereses | No aparece en recomendaciones | Sí | La lista propia puede consultarse; no genera recomendaciones |

El campo de API `is_public` corresponde a la columna `perfiles.visibilidad_publica`. La preferencia de perfil no cambia la visibilidad de los grupos que administra.

### 2.4 Visibilidad de grupos

| Estado | Quién puede consultar | Qué puede consultar |
|---|---|---|
| Grupo privado (`es_descubrible = false`) | Miembros/antiguos miembros según sus permisos de conversación | Detalle de conversación y contenido según periodo de membresía |
| Grupo descubrible (`es_descubrible = true`) | Miembros y usuarios verificados externos | Externos: nombre, descripción, intereses, cantidad de integrantes y plazas; nunca lista de miembros ni mensajes |
| Grupo archivado | Usuarios con historial de membresía, según su periodo | Historial permitido en solo lectura; nunca aparece en Descubrir |
| Grupo completo | Usuarios verificados externos | La misma información pública, con `Grupo completo`; no admite nuevas solicitudes |

El campo de API `is_discoverable` corresponde a `conversaciones.es_descubrible`.

---

## 3. Funciones auxiliares de autorización

Las funciones viven en el esquema no expuesto `app`. Las funciones que consultan membresías o perfiles bajo RLS se diseñan como `SECURITY DEFINER` únicamente cuando hace falta evitar recursión o leer el dato mínimo de autorización. Deben tener `search_path` fijo, referencias de tablas totalmente cualificadas, `EXECUTE` revocado de `PUBLIC` y grants explícitos.

### 3.1 Identidad del actor y verificación

```sql
create schema if not exists app;

create or replace function app.current_actor_id()
returns uuid
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
```

`app.current_actor_id()` es `SECURITY DEFINER` propiedad del rol de migraciones, con `search_path` fijo. El propietario tiene `USAGE` sobre `auth` y `EXECUTE` sobre `auth.uid()` (verificado en el proyecto); `chatly_app` no hereda `authenticated` y solo recibe `EXECUTE` sobre esta función y las demás funciones de `app`.

El backend debe ejecutar `set_config('app.current_user_id', :uid, true)` dentro de cada transacción autenticada. El tercer argumento `true` limita el valor a la transacción y evita que se filtre al siguiente usuario que reutilice la conexión del pool.

### 3.2 Membresía e historial

```sql
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
```

### 3.3 Alta inicial de membresía

```sql
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
```

La función evita que un usuario se autoinserte en una conversación ajena aprovechando que RLS oculta las membresías existentes. El servicio debe insertar al creador de un grupo como `admin` en la misma transacción de creación.

### 3.4 Capacidad disponible de grupo

```sql
create or replace function app.group_has_capacity(p_conversacion_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.conversaciones c
        where c.id = p_conversacion_id
          and c.tipo = 'group'
          and c.archivada = false
          and c.eliminado_en is null
          and (select app.is_verified_actor())
          and (
              select count(*)
              from public.miembros_conversacion m
              where m.conversacion_id = c.id
                and m.salido_en is null
                and m.estado = 'active'
          ) < 10
    );
$$;
```

La función permite validar capacidad sin que RLS oculte al solicitante las filas de membresía de un grupo al que todavía no pertenece. El servicio sigue bloqueando la fila de `conversaciones` en la transacción para evitar carreras.

La API también necesita calcular `members_count` y `available_places` para el resumen público del grupo. Los usuarios externos no pueden leer `miembros_conversacion`, por lo que el backend obtiene únicamente el agregado mediante esta función:

```sql
create or replace function app.discoverable_group_member_count(p_conversacion_id uuid)
returns integer
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select case
        when (select app.is_verified_actor())
         and exists (
             select 1
             from public.conversaciones c
             where c.id = p_conversacion_id
               and c.tipo = 'group'
               and c.es_descubrible = true
               and c.archivada = false
               and c.eliminado_en is null
         )
        then (
            select count(*)::integer
            from public.miembros_conversacion m
            where m.conversacion_id = p_conversacion_id
              and m.salido_en is null
              and m.estado = 'active'
        )
        else null
    end;
$$;
```

La función devuelve solo un entero; no revela IDs, alias ni la lista de integrantes. La API calcula las plazas como `10 - members_count` y determina si el grupo está completo a partir del mismo valor. Para grupos privados o archivados devuelve `NULL` a usuarios externos.

### 3.5 Topics de Realtime

```sql
create or replace function app.topic_conversation_id()
returns uuid
language sql
stable
set search_path = public, pg_temp
as $$
    select case
        when realtime.topic() ~ '^conversation:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        then split_part(realtime.topic(), ':', 2)::uuid
    end;
$$;

create or replace function app.topic_user_id()
returns uuid
language sql
stable
set search_path = public, pg_temp
as $$
    select case
        when realtime.topic() ~ '^(presence|notifications):user:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        then split_part(realtime.topic(), ':', 3)::uuid
    end;
$$;

create or replace function app.can_view_presence(p_usuario_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1
        from public.perfiles p
        where p.id = p_usuario_id
          and p.eliminado_en is null
          and p.correo_verificado_en is not null
          and (select app.is_verified_actor())
          and (
              p.id = (select app.current_actor_id())
              or p.visibilidad_publica = true
          )
    );
$$;
```

`app.topic_user_id()` se usa solo para topics de presencia y notificaciones. `app.can_view_presence()` permite consultar presencia solo a actores verificados y solo para perfiles objetivo verificados; los terceros necesitan además que el perfil objetivo tenga visibilidad pública activa.

### 3.6 Lecturas sociales limitadas por contexto

La API muestra al administrador únicamente los intereses que el solicitante comparte con la temática del grupo. Esto debe funcionar incluso si el solicitante tiene `visibilidad_publica = false`, sin abrir la lectura general de `intereses_usuario`. La siguiente función devuelve exclusivamente la intersección para una solicitud pendiente que pertenece a un grupo administrado por el actor:

```sql
create or replace function app.shared_interests_for_join_request(p_solicitud_id uuid)
returns table (interes_id uuid, nombre text)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select i.id, i.nombre
    from public.solicitudes_union s
    join public.conversaciones c
      on c.id = s.conversacion_id
    join public.intereses_conversacion ig
      on ig.conversacion_id = s.conversacion_id
    join public.intereses_usuario iu
      on iu.usuario_id = s.solicitante_id
     and iu.interes_id = ig.interes_id
    join public.intereses i
      on i.id = ig.interes_id
    where s.id = p_solicitud_id
      and s.estado = 'pending'
      and c.tipo = 'group'
      and c.es_descubrible = true
      and c.archivada = false
      and c.eliminado_en is null
      and i.activo = true
      and (select app.is_verified_actor())
      and (select app.is_active_admin(s.conversacion_id))
    order by lower(i.nombre), i.id;
$$;
```

La función no devuelve los demás intereses personales del solicitante ni permite consultar solicitudes de otro grupo. Solo `chatly_app` puede ejecutarla; el endpoint correspondiente sigue siendo `GET /api/conversations/{conversation_id}/join-requests`.

### 3.7 Revocación de funciones

```sql
revoke all on function app.current_actor_id() from public;
revoke all on function app.is_verified_actor() from public;
revoke all on function app.has_membership(uuid) from public;
revoke all on function app.has_period(uuid, timestamptz) from public;
revoke all on function app.is_active_member(uuid) from public;
revoke all on function app.is_active_admin(uuid) from public;
revoke all on function app.can_bootstrap_membership(uuid, uuid) from public;
revoke all on function app.group_has_capacity(uuid) from public;
revoke all on function app.discoverable_group_member_count(uuid) from public;
revoke all on function app.shared_interests_for_join_request(uuid) from public;
revoke all on function app.topic_conversation_id() from public;
revoke all on function app.topic_user_id() from public;
revoke all on function app.can_view_presence(uuid) from public;
revoke all on function app.resolve_pending_request_after_joining_other_group(uuid, uuid) from public;
revoke all on function app.expire_pending_join_requests() from public;
revoke all on function app.publish_social_event(text, uuid, jsonb) from public;

grant usage on schema app to authenticated, chatly_app;
grant execute on function app.current_actor_id() to authenticated, chatly_app;
grant execute on function app.is_verified_actor() to authenticated, chatly_app;
grant execute on function app.has_membership(uuid) to authenticated, chatly_app;
grant execute on function app.has_period(uuid, timestamptz) to authenticated, chatly_app;
grant execute on function app.is_active_member(uuid) to authenticated, chatly_app;
grant execute on function app.is_active_admin(uuid) to chatly_app;
grant execute on function app.can_bootstrap_membership(uuid, uuid) to chatly_app;
grant execute on function app.group_has_capacity(uuid) to chatly_app;
grant execute on function app.discoverable_group_member_count(uuid) to chatly_app;
grant execute on function app.shared_interests_for_join_request(uuid) to chatly_app;
grant execute on function app.topic_conversation_id() to authenticated;
grant execute on function app.topic_user_id() to authenticated;
grant execute on function app.can_view_presence(uuid) to authenticated;
grant execute on function app.resolve_pending_request_after_joining_other_group(uuid, uuid) to chatly_app;
grant execute on function app.expire_pending_join_requests() to chatly_app;
grant execute on function app.publish_social_event(text, uuid, jsonb) to chatly_app;
```

**Precauciones de `SECURITY DEFINER`:** las funciones deben pertenecer a un rol controlado, no ejecutan SQL dinámico, fijan `search_path`, revocan `PUBLIC` y devuelven solo lo mínimo necesario (booleanos, UUID de topic, la intersección autorizada de intereses o un `void` de publicación). `app.publish_social_event` valida el evento contra una lista blanca y construye el topic; no acepta un topic arbitrario. Ejecutar `supabase db advisors` y pruebas de aislamiento antes de aprobarlas.

---

## 4. Matriz funcional

Leyenda: **Sí** = permitido con sus reglas; **No** = denegado; **Período** = filas dentro de periodos de membresía; **Propio** = únicamente datos del actor; **Admin** = administrador activo del grupo.

| Operación | Verificado | No verificado | Miembro activo | Antiguo / expulsado | Ajeno |
|---|---:|---:|---:|---:|---:|
| Consultar perfil propio | Sí | Sí | — | — | — |
| Editar perfil propio | Sí | Sí | — | — | — |
| Cambiar `visibilidad_publica` | Propio | Propio | — | — | — |
| Consultar intereses propios | Sí | Sí, en su registro/perfil propio | — | — | — |
| Consultar intereses de otro perfil | Si el perfil objetivo está verificado y `visibilidad_publica = true` | No | — | — | — |
| Aparecer en recomendaciones de personas | Si el perfil objetivo está verificado, es público, tiene intereses y cumple filtros | No | — | — | — |
| Buscar usuario por alias/correo | Sí | No | — | — | — |
| Ver grupo descubrible | Sí | No | Sí | Si tiene historial de membresía | No si es privado |
| Ver lista de integrantes de un grupo | No si es externo | No | Sí | Solo mediante el detalle autorizado de conversación, según API | No |
| Ver mensajes de grupo | No si es externo | No | Período | Período | No |
| Configurar descubribilidad/intereses del grupo | — | — | Admin | No | No |
| Crear solicitud de unión | Sí | No | Si no es miembro | Si no es miembro | — |
| Ver su solicitud pendiente | Propio | No | Propio | Propio | — |
| Listar solicitudes recibidas | Admin del grupo | No | Admin | No | No |
| Aceptar/rechazar solicitud | Admin | No | Admin | No | No |
| Cancelar solicitud propia | No | No | No | No | — |
| Ver historial «Mis solicitudes» | No hay interfaz | No | No hay interfaz | No hay interfaz | — |
| Enviar mensaje/reaccionar/votar | — | — | Sí, según reglas | No | No |
| Enviar `typing` | — | — | Sí | No | No |
| Publicar presencia propia | Sí | No | — | — | — |
| Ver presencia de otro usuario | Si ambos perfiles están verificados y el objetivo es público | No | — | — | — |
| Leer auditoría | No desde la app | No | — | — | — |

**Aclaración sobre el perfil:** al desactivar `visibilidad_publica`, se ocultan los intereses y las recomendaciones. La búsqueda directa sigue mostrando nombre, alias y fotografía. La fecha de nacimiento exacta nunca se devuelve a terceros; la edad y el género siguen las reglas de `ProfilePublic` del contrato de API.

---

## 5. Políticas RLS por tabla

Todas las tablas de negocio deben tener RLS habilitado. Las políticas siguientes describen el acceso lógico por rol. Los `GRANT` de la sección 8 son obligatorios: una política RLS no concede por sí sola privilegios SQL.

### 5.1 `perfiles`

```sql
alter table public.perfiles enable row level security;

create policy perfiles_select_backend on public.perfiles
    for select to chatly_app
    using (
        id = (select app.current_actor_id())
        or (
            (select app.is_verified_actor())
            and eliminado_en is null
        )
    );

create policy perfiles_insert_propio on public.perfiles
    for insert to chatly_app
    with check (id = (select app.current_actor_id()));

create policy perfiles_update_propio on public.perfiles
    for update to chatly_app
    using (id = (select app.current_actor_id()))
    with check (id = (select app.current_actor_id()));
```

Reglas:

- El navegador no recibe `SELECT` directo sobre `perfiles` ni sobre `app.perfiles_publicos`; los perfiles se sirven mediante API.
- El backend puede leer el perfil del actor y, para una búsqueda/consulta autorizada, perfiles no eliminados cuando el actor está verificado. La API controla qué campos devuelve.
- `fecha_nacimiento` solo se devuelve en `ProfileMe`. No se devuelve el correo en perfiles públicos ni búsquedas.
- `visibilidad_publica` se puede cambiar únicamente por el propietario del perfil. No controla la descubribilidad de los grupos que administra.
- No hay política de `DELETE`; Q42 excluye eliminación de cuentas en V1.

### 5.2 `contactos_usuario`

```sql
alter table public.contactos_usuario enable row level security;

create policy contactos_insert_backend on public.contactos_usuario
    for insert to chatly_app
    with check (usuario_id = (select app.current_actor_id()));

create policy contactos_update_backend on public.contactos_usuario
    for update to chatly_app
    using (usuario_id = (select app.current_actor_id()))
    with check (usuario_id = (select app.current_actor_id()));
```

- No existe política de `SELECT`: ni el navegador ni `chatly_app` pueden leer la tabla directamente.
- La búsqueda exacta por correo utiliza `app.buscar_usuario_por_correo(text)`, función controlada que devuelve únicamente `usuario_id`, alias, nombre visible y ruta de avatar; nunca devuelve el correo.
- La función debe exigir actor autenticado y verificado, excluir al propio usuario y filtrar perfiles eliminados.

### 5.3 `conversaciones`

```sql
alter table public.conversaciones enable row level security;

-- Navegador/Realtime: solo miembros activos reciben cambios de una conversación.
create policy conversaciones_select_realtime_activo on public.conversaciones
    for select to authenticated
    using ((select app.is_active_member(id)));

-- Backend: miembros actuales o históricos pueden acceder mediante la API.
create policy conversaciones_select_backend_membresia on public.conversaciones
    for select to chatly_app
    using ((select app.has_membership(id)));

-- Backend: grupos descubribles pueden consultarse desde Descubrir por usuarios verificados.
create policy conversaciones_select_backend_descubribles on public.conversaciones
    for select to chatly_app
    using (
        tipo = 'group'
        and es_descubrible = true
        and archivada = false
        and eliminado_en is null
        and (select app.is_verified_actor())
    );

create policy conversaciones_insert_backend on public.conversaciones
    for insert to chatly_app
    with check (
        creado_por = (select app.current_actor_id())
        and (select app.is_verified_actor())
    );

create policy conversaciones_update_admin on public.conversaciones
    for update to chatly_app
    using ((select app.is_active_admin(id)))
    with check ((select app.is_active_admin(id)));
```

Reglas:

- `authenticated` solo lee filas de conversaciones donde el actor es miembro activo; esta política permite Postgres Changes sin mantener acceso en vivo a quien ya no es miembro.
- `chatly_app` puede recuperar conversaciones para miembros actuales o históricos. Para grupos externos solo puede consultar grupos activos y descubribles.
- La API de Descubrir devuelve a usuarios externos únicamente nombre, descripción, intereses, cantidad de integrantes, plazas y estado de grupo completo. No devuelve integrantes ni mensajes.
- Para `members_count` y `available_places`, el backend utiliza `app.discoverable_group_member_count(uuid)`, que devuelve solo el agregado de un grupo activo y descubrible; no se abre `miembros_conversacion` a usuarios externos.
- Solo el administrador activo modifica nombre, descripción, intereses y `es_descubrible`.
- Desactivar la descubribilidad y rechazar las solicitudes pendientes del grupo debe hacerse en una misma transacción.
- Cuando sale el último integrante (que necesariamente es el último administrador activo), el servicio marca primero la conversación como archivada y después cierra la última membresía, dentro de la misma transacción. Así la política `conversaciones_update_admin` todavía puede validar al administrador durante el `UPDATE` de archivo.
- El límite de 10 integrantes se valida en servicio con bloqueo de la fila de `conversaciones`; RLS no sustituye esa validación concurrente.

### 5.4 `miembros_conversacion`

```sql
alter table public.miembros_conversacion enable row level security;

create policy miembros_select_realtime_activos on public.miembros_conversacion
    for select to authenticated
    using ((select app.is_active_member(conversacion_id)));

create policy miembros_select_backend on public.miembros_conversacion
    for select to chatly_app
    using ((select app.has_membership(conversacion_id)));

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
    );

create policy miembros_update_backend on public.miembros_conversacion
    for update to chatly_app
    using (
        (select app.is_active_admin(conversacion_id))
        or usuario_id = (select app.current_actor_id())
    )
    with check (
        (select app.is_active_admin(conversacion_id))
        or usuario_id = (select app.current_actor_id())
    );
```

**Protección adicional de actualizaciones:** mantener un trigger que impida cambiar `conversacion_id`, `usuario_id` o `unido_en`; impida reabrir una fila cerrada; permita cambio de rol solo al administrador; y limite al propio usuario a cerrar su periodo voluntariamente con `estado = 'left'`, `salido_en` establecido por el servidor y `retirado_por = NULL`. El usuario no puede marcarse como expulsado ni cambiar su rol. La expulsión (`estado = 'removed'`, `retirado_por` identificado) requiere administrador activo.

Reglas:

- Cada entrada crea un periodo nuevo; una salida/expulsión cierra el periodo y nunca lo reactiva.
- Una sola membresía activa por usuario y conversación, garantizada por índice único parcial.
- Solo un administrador activo por grupo, también garantizado por índice único parcial.
- Los usuarios externos no consultan esta tabla ni reciben la lista de miembros de un grupo descubrible.
- `chatly_app` obtiene la lista para el detalle de conversaciones de miembros y aplica las reglas del contrato. No se expone esa lista en los endpoints externos de Descubrir.

### 5.5 `preferencias_conversacion`

```sql
alter table public.preferencias_conversacion enable row level security;

create policy preferencias_select_propio on public.preferencias_conversacion
    for select to chatly_app
    using (usuario_id = (select app.current_actor_id()));

create policy preferencias_insert_propio on public.preferencias_conversacion
    for insert to chatly_app
    with check (usuario_id = (select app.current_actor_id()));

create policy preferencias_update_propio on public.preferencias_conversacion
    for update to chatly_app
    using (usuario_id = (select app.current_actor_id()))
    with check (usuario_id = (select app.current_actor_id()));
```

- La ocultación es individual. No altera la conversación ni las preferencias de otros usuarios.
- No se concede acceso directo a `authenticated`.

### 5.6 `mensajes`

```sql
alter table public.mensajes enable row level security;

create policy mensajes_select_por_periodo on public.mensajes
    for select to authenticated, chatly_app
    using ((select app.has_period(conversacion_id, creado_en)));

create policy mensajes_insert_backend on public.mensajes
    for insert to chatly_app
    with check (
        (select app.is_active_member(conversacion_id))
        and (
            (tipo in ('text','poll') and autor_id = (select app.current_actor_id()))
            or tipo = 'system'
        )
    );

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
    );
```

- La lectura se limita al periodo de membresía que cubre `creado_en`.
- Los borrados son actualizaciones de `eliminado_en`; no se concede `DELETE`.
- Los mensajes de sistema los genera el servicio para eventos de grupo. No se permiten mensajes de sistema creados desde el navegador.
- Si `eliminado_en IS NOT NULL`, la API no devuelve `contenido` y presenta el marcador acordado.

### 5.7 `versiones_mensaje`

```sql
alter table public.versiones_mensaje enable row level security;

create policy versiones_select_backend_autor on public.versiones_mensaje
    for select to chatly_app
    using (
        exists (
            select 1
            from public.mensajes m
            where m.id = mensaje_id
              and m.autor_id = (select app.current_actor_id())
        )
    );

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
    );
```

- No existe interfaz de consulta del historial de ediciones en V1.
- Las versiones anteriores se conservan para trazabilidad. No se exponen en las consultas normales del chat.

### 5.8 `reacciones_mensaje`

```sql
alter table public.reacciones_mensaje enable row level security;

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
    );

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
    );

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
    with check (usuario_id = (select app.current_actor_id()));
```

- Una reacción activa por usuario y mensaje; cambiar emoji reemplaza la reacción vigente.
- Los antiguos integrantes solo pueden consultar reacciones correspondientes a mensajes de sus periodos; no pueden crear, cambiar ni eliminar reacciones.

### 5.9 `encuestas`

```sql
alter table public.encuestas enable row level security;

create policy encuestas_select_por_periodo on public.encuestas
    for select to authenticated, chatly_app
    using (
        exists (
            select 1
            from public.mensajes m
            where m.id = mensaje_id
              and (select app.has_period(m.conversacion_id, m.creado_en))
        )
    );

create policy encuestas_insert_backend on public.encuestas
    for insert to chatly_app
    with check (
        creada_por = (select app.current_actor_id())
        and (select app.is_active_member(conversacion_id))
        and exists (
            select 1
            from public.mensajes m
            where m.id = mensaje_id
              and m.tipo = 'poll'
              and m.autor_id = (select app.current_actor_id())
        )
    );

create policy encuestas_update_backend on public.encuestas
    for update to chatly_app
    using (
        (select app.is_active_member(conversacion_id))
        and (
            creada_por = (select app.current_actor_id())
            or (select app.is_active_admin(conversacion_id))
        )
    )
    with check (
        (select app.is_active_member(conversacion_id))
        and (
            creada_por = (select app.current_actor_id())
            or (select app.is_active_admin(conversacion_id))
        )
    );
```

- El servicio aplica las condiciones finas: solo el creador edita antes del primer voto; el administrador solo puede cerrar cuando el creador ya no pertenece al grupo.
- Las encuestas cerradas no admiten votos ni cambios.

### 5.10 `opciones_encuesta`

```sql
alter table public.opciones_encuesta enable row level security;

create policy opciones_select_por_periodo on public.opciones_encuesta
    for select to authenticated, chatly_app
    using (
        exists (
            select 1
            from public.encuestas e
            join public.mensajes m on m.id = e.mensaje_id
            where e.id = encuesta_id
              and (select app.has_period(m.conversacion_id, m.creado_en))
        )
    );

create policy opciones_insert_backend on public.opciones_encuesta
    for insert to chatly_app
    with check (
        exists (
            select 1
            from public.encuestas e
            where e.id = encuesta_id
              and e.creada_por = (select app.current_actor_id())
              and (select app.is_active_member(e.conversacion_id))
        )
    );

create policy opciones_update_antes_de_votos on public.opciones_encuesta
    for update to chatly_app
    using (
        exists (
            select 1
            from public.encuestas e
            where e.id = encuesta_id
              and e.creada_por = (select app.current_actor_id())
              and (select app.is_active_member(e.conversacion_id))
              and not exists (
                  select 1 from public.votos_encuesta v where v.encuesta_id = e.id
              )
        )
    )
    with check (
        exists (
            select 1
            from public.encuestas e
            where e.id = encuesta_id
              and e.creada_por = (select app.current_actor_id())
              and (select app.is_active_member(e.conversacion_id))
              and not exists (
                  select 1 from public.votos_encuesta v where v.encuesta_id = e.id
              )
        )
    );
```

- Las opciones solo se modifican por el creador antes del primer voto.
- No se concede escritura a `authenticated`.

### 5.11 `votos_encuesta`

```sql
alter table public.votos_encuesta enable row level security;

create policy votos_select_por_periodo on public.votos_encuesta
    for select to authenticated, chatly_app
    using (
        exists (
            select 1
            from public.encuestas e
            join public.mensajes m on m.id = e.mensaje_id
            where e.id = encuesta_id
              and (select app.has_period(m.conversacion_id, m.creado_en))
        )
    );

create policy votos_insert_propio on public.votos_encuesta
    for insert to chatly_app
    with check (
        usuario_id = (select app.current_actor_id())
        and exists (
            select 1
            from public.encuestas e
            where e.id = encuesta_id
              and e.estado = 'open'
              and (select app.is_active_member(e.conversacion_id))
        )
    );

create policy votos_update_propio on public.votos_encuesta
    for update to chatly_app
    using (
        usuario_id = (select app.current_actor_id())
        and exists (
            select 1
            from public.encuestas e
            where e.id = encuesta_id
              and e.estado = 'open'
              and (select app.is_active_member(e.conversacion_id))
        )
    )
    with check (usuario_id = (select app.current_actor_id()));
```

- Un voto vigente por usuario y encuesta mediante restricción única.
- Cambiar el voto actualiza la fila existente; no se crea un segundo voto vigente.
- Los votos siguen contando aunque el usuario abandone el grupo, pero este ya no puede modificarlos mientras no sea miembro activo.

### 5.12 `registros_auditoria`

```sql
alter table public.registros_auditoria enable row level security;

create policy auditoria_insert_backend on public.registros_auditoria
    for insert to chatly_app
    with check (
        actor_id is null
        or actor_id = (select app.current_actor_id())
    );
```

- No hay políticas de `SELECT`, `UPDATE` ni `DELETE` desde la aplicación.
- `actor_id IS NULL` se reserva para operaciones automáticas controladas, como la expiración programada de solicitudes.
- Las herramientas administrativas pueden inspeccionar los registros fuera de la aplicación, mediante un rol separado.

---

## 6. Políticas RLS para descubrimiento social

Las tablas sociales no se exponen directamente al navegador. El backend las consulta y devuelve DTOs filtrados, pero RLS limita también al rol `chatly_app` para que un error de servicio no convierta una consulta social en un directorio privado.

### 6.1 `categorias_interes` y `intereses`

```sql
alter table public.categorias_interes enable row level security;
alter table public.intereses enable row level security;

create policy categorias_select_activas_backend on public.categorias_interes
    for select to chatly_app
    using (activa = true and (select app.current_actor_id()) is not null);

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
    );
```

- `authenticated` no tiene `SELECT` directo sobre el catálogo; lo recibe mediante `GET /api/interests`.
- El endpoint público no usa esas políticas: lee con `app.catalogo_intereses()`, función `SECURITY DEFINER` creada en `0005b_intereses` (mismo patrón que `app.alias_exists`). Es el único mecanismo que devuelve el catálogo sin actor, porque el registro lo consume antes de que exista sesión (Q15, Q128).
- No se conceden `INSERT`, `UPDATE` ni `DELETE` a `chatly_app`. El catálogo se mantiene mediante migraciones y semillas.
- Las categorías ordenan la interfaz; el usuario selecciona intereses concretos, no categorías completas.

### 6.2 `intereses_usuario`

```sql
alter table public.intereses_usuario enable row level security;

create policy intereses_usuario_select_backend on public.intereses_usuario
    for select to chatly_app
    using (
        usuario_id = (select app.current_actor_id())
        or exists (
            select 1
            from public.perfiles p
            where p.id = usuario_id
              and p.visibilidad_publica = true
              and p.correo_verificado_en is not null
              and p.eliminado_en is null
              and (select app.is_verified_actor())
        )
    );

create policy intereses_usuario_insert_propio on public.intereses_usuario
    for insert to chatly_app
    with check (usuario_id = (select app.current_actor_id()));

create policy intereses_usuario_delete_propio on public.intereses_usuario
    for delete to chatly_app
    using (usuario_id = (select app.current_actor_id()));
```

Reglas:

- El propietario puede consultar y reemplazar su propia selección, incluso durante el registro opcional.
- La política de lectura de intereses de terceros que aparece arriba **todavía no está creada**: depende de `app.is_verified_actor()`, que se añade en `0013_descubrimiento_social`. En `0005b_intereses` solo existe la selección propia (`intereses_usuario_select_propio`, `intereses_usuario_insert_propio` e `intereses_usuario_delete_propio`).
- Otros usuarios solo pueden obtener los intereses de perfiles con `visibilidad_publica = true` y si el actor está verificado.
- Con visibilidad desactivada, los intereses no se muestran en el perfil público ni se utilizan para recomendar al usuario.
- El límite de 10 intereses se valida en servicio dentro de una transacción que bloquea `perfiles` del actor. El catálogo debe estar activo.
- El reemplazo de la tabla de relación elimina las asociaciones anteriores y crea las nuevas en una sola transacción; ese borrado de filas de relación no es un borrado de mensajes ni de contenido de usuario. Se registra auditoría.
- No se concede acceso directo a `authenticated`.

### 6.3 `intereses_conversacion`

```sql
alter table public.intereses_conversacion enable row level security;

create policy intereses_conversacion_select_backend on public.intereses_conversacion
    for select to chatly_app
    using (
        exists (
            select 1
            from public.conversaciones c
            where c.id = conversacion_id
              and c.tipo = 'group'
              and (
                  (select app.has_membership(c.id))
                  or (
                      c.tipo = 'group'
                      and c.es_descubrible = true
                      and c.archivada = false
                      and c.eliminado_en is null
                      and (select app.is_verified_actor())
                  )
              )
        )
    );

create policy intereses_conversacion_insert_admin on public.intereses_conversacion
    for insert to chatly_app
    with check (
        (select app.is_active_admin(conversacion_id))
        and exists (
            select 1
            from public.conversaciones c
            where c.id = conversacion_id
              and c.tipo = 'group'
              and c.archivada = false
        )
        and exists (
            select 1
            from public.intereses i
            where i.id = interes_id and i.activo = true
        )
    );

create policy intereses_conversacion_delete_admin on public.intereses_conversacion
    for delete to chatly_app
    using ((select app.is_active_admin(conversacion_id)));
```

Reglas:

- El administrador activo es el único que puede cambiar los intereses de su grupo.
- Un actor externo solo puede leer intereses asociados a un grupo activo y descubrible.
- El servicio bloquea la fila de `conversaciones`, valida entre 1 y 5 intereses al publicar y mantiene ese rango al editar el grupo publicado.
- Los intereses de un grupo privado no se devuelven a usuarios externos.
- Los cambios se reflejan en la siguiente apertura/actualización de Descubrir; no se envían listas de intereses por Realtime.

### 6.4 `solicitudes_union`

```sql
alter table public.solicitudes_union enable row level security;

create policy solicitudes_select_solicitante_o_admin on public.solicitudes_union
    for select to chatly_app
    using (
        (select app.is_verified_actor())
        and estado = 'pending'
        and (
            solicitante_id = (select app.current_actor_id())
            or (select app.is_active_admin(conversacion_id))
        )
    );

create policy solicitudes_insert_solicitante on public.solicitudes_union
    for insert to chatly_app
    with check (
        solicitante_id = (select app.current_actor_id())
        and (select app.is_verified_actor())
        and estado = 'pending'
        and motivo_resolucion is null
        and resuelta_en is null
        and exists (
            select 1
            from public.conversaciones c
            where c.id = conversacion_id
              and c.tipo = 'group'
              and c.es_descubrible = true
              and c.archivada = false
              and c.eliminado_en is null
        )
        and not (select app.is_active_member(conversacion_id))
        and (select app.group_has_capacity(conversacion_id))
    );

create policy solicitudes_update_resolucion on public.solicitudes_union
    for update to chatly_app
    using (
        estado = 'pending'
        and (select app.is_active_admin(conversacion_id))
    )
    with check (
        estado in ('accepted','rejected')
        and resuelta_en is not null
        and motivo_resolucion is not null
        and resuelta_por = (select app.current_actor_id())
        and (select app.is_active_admin(conversacion_id))
    );
```

Reglas obligatorias del servicio, además de RLS:

- `solicitante_id` se deriva del actor autenticado; nunca se acepta como identidad desde el body.
- Solo se solicita un grupo activo y descubrible. No es necesario compartir intereses con el grupo.
- El solicitante no puede ser ya miembro del grupo.
- El índice único parcial `uq_solicitudes_union_pendiente_usuario` garantiza una sola solicitud pendiente global por usuario.
- Una solicitud pendiente no se cancela y no existe estado `cancelled`.
- La solicitud vence a los 14 días; el proceso automático solo puede mover solicitudes vencidas a `expired`.
- Solo un rechazo manual genera una espera de siete días para ese mismo grupo. Los rechazos automáticos por `group_private`, `group_full` o `joined_other_group` no generan esa espera.
- El solicitante consulta únicamente su solicitud pendiente; no hay pantalla «Mis solicitudes» ni historial de solicitudes resueltas.
- El administrador activo consulta las solicitudes pendientes de su grupo, ordenadas de la más antigua a la más reciente. No recibe correo electrónico.
- El administrador ve fotografía, nombre, alias, intereses compartidos con el grupo y fecha de solicitud. La entrega de esos intereses compartidos es una excepción limitada al contexto de la solicitud; no vuelve público el perfil ni incorpora al solicitante a recomendaciones de personas.
- Como `intereses_usuario` oculta las selecciones de perfiles privados, el backend obtiene esa intersección únicamente mediante `app.shared_interests_for_join_request(uuid)`, que valida que la solicitud siga pendiente y que el actor sea administrador activo del grupo. No entrega el resto de los intereses personales.
- Las transiciones se ejecutan dentro de las transacciones definidas en `database-schema.md` §17.6. La política RLS permite al administrador resolver una fila pendiente, pero es el servicio quien garantiza que la aceptación y la creación de la membresía ocurran atómicamente.

**Transiciones especiales:**

1. Aceptar una solicitud crea la membresía y cambia el estado a `accepted` en una sola transacción.
2. Si el grupo ya tiene 10 integrantes, no se crea la membresía y se marca la solicitud `rejected` con motivo `group_full`.
3. Si el administrador añade directamente al solicitante al mismo grupo, la solicitud pasa a `accepted` con motivo `direct_add_same_group`; se crea una sola membresía.
4. Si el usuario es añadido a otro grupo, su solicitud pendiente anterior pasa a `rejected` con motivo `joined_other_group`. Como el actor que realiza la incorporación puede ser el administrador del grupo de destino y no el administrador del grupo solicitado, esta transición debe ejecutarse mediante `app.resolve_pending_request_after_joining_other_group()`, que valida que el actor es administrador activo del grupo de destino y que el solicitante ya es miembro activo allí.
5. Cuando el grupo pasa a privado, el administrador activo puede rechazar sus solicitudes pendientes con motivo `group_private` en la misma transacción.
6. Al alcanzar el máximo de 10 integrantes, el administrador/servicio resuelve las demás solicitudes pendientes de ese grupo con motivo `group_full`.
7. El proceso de expiración utiliza `app.expire_pending_join_requests()`, función `SECURITY DEFINER` sin parámetros y restringida a `chatly_app`; solo expira solicitudes vencidas, registra auditoría y no ofrece una función genérica para actualizar cualquier solicitud.

### 6.5 Funciones controladas para transiciones automáticas

Dos transiciones no deben autorizarse como una actualización directa del solicitante: el rechazo por incorporación a otro grupo y la expiración automática. Se encapsulan en funciones `SECURITY DEFINER` pequeñas, con validación de contexto y sin parámetros que permitan cambiar libremente el estado de una solicitud.

**Rechazo por incorporación a otro grupo:**

```sql
create or replace function app.resolve_pending_request_after_joining_other_group(
    p_solicitante_id uuid,
    p_conversacion_destino_id uuid
)
returns uuid
language plpgsql
security definer
set search_path = public, app, pg_temp
as $$
declare
    v_actor_id uuid := app.current_actor_id();
    v_solicitud_id uuid;
begin
    if v_actor_id is null
       or not app.is_active_admin(p_conversacion_destino_id) then
        raise exception 'Solo el administrador activo del grupo de destino puede resolver esta transición'
            using errcode = '42501';
    end if;

    if not exists (
        select 1
        from public.miembros_conversacion m
        where m.conversacion_id = p_conversacion_destino_id
          and m.usuario_id = p_solicitante_id
          and m.salido_en is null
          and m.estado = 'active'
    ) then
        raise exception 'El usuario todavía no pertenece al grupo de destino'
            using errcode = '42501';
    end if;

    update public.solicitudes_union s
       set estado = 'rejected',
           motivo_resolucion = 'joined_other_group',
           resuelta_en = now(),
           resuelta_por = v_actor_id,
           actualizado_en = now()
     where s.solicitante_id = p_solicitante_id
       and s.estado = 'pending'
       and s.conversacion_id <> p_conversacion_destino_id
    returning s.id into v_solicitud_id;

    if v_solicitud_id is not null then
        insert into public.registros_auditoria (
            actor_id, accion, tipo_entidad, entidad_id, conversacion_id, valores_nuevos
        )
        select v_actor_id, 'join_request_rejected_joined_other_group',
               'solicitudes_union', v_solicitud_id, s.conversacion_id,
               jsonb_build_object('estado', 'rejected', 'motivo_resolucion', 'joined_other_group')
        from public.solicitudes_union s
        where s.id = v_solicitud_id;
    end if;

    return v_solicitud_id;
end;
$$;

revoke all on function app.resolve_pending_request_after_joining_other_group(uuid, uuid) from public;
grant execute on function app.resolve_pending_request_after_joining_other_group(uuid, uuid) to chatly_app;
```

El servicio llama esta función solo después de crear la membresía en el grupo de destino, dentro de la misma transacción. La función comprueba que el actor sea administrador del grupo de destino y que el solicitante ya sea miembro activo allí. La función no permite que un usuario rechace por sí mismo su solicitud.

**Expiración automática:**

```sql
create or replace function app.expire_pending_join_requests()
returns integer
language plpgsql
security definer
set search_path = public, app, pg_temp
as $$
declare
    v_row record;
    v_total integer := 0;
begin
    for v_row in
        update public.solicitudes_union s
           set estado = 'expired',
               motivo_resolucion = 'expired',
               resuelta_en = now(),
               resuelta_por = null,
               actualizado_en = now()
         where s.estado = 'pending'
           and s.vence_en <= now()
        returning s.id, s.conversacion_id, s.solicitante_id
    loop
        insert into public.registros_auditoria (
            actor_id, accion, tipo_entidad, entidad_id, conversacion_id, valores_nuevos
        ) values (
            null, 'join_request_expired', 'solicitudes_union', v_row.id, v_row.conversacion_id,
            jsonb_build_object('estado', 'expired', 'motivo_resolucion', 'expired')
        );

        perform app.publish_social_event(
            'join_request.resolved',
            v_row.solicitante_id,
            jsonb_build_object(
                'request_id', v_row.id,
                'conversation_id', v_row.conversacion_id,
                'status', 'expired',
                'reason_code', 'expired',
                'sent_at', now()
            )
        );

        v_total := v_total + 1;
    end loop;

    return v_total;
end;
$$;

revoke all on function app.expire_pending_join_requests() from public;
grant execute on function app.expire_pending_join_requests() to chatly_app;
```

El job de `pg_cron` ejecuta únicamente esta función como `chatly_app`; el rol no recibe permiso general para actualizar solicitudes. La función no acepta identificadores ni estados desde el cliente y solo expira solicitudes cuyo vencimiento ya ocurrió. Publica el aviso con `app.publish_social_event(...)` en la misma transacción.

**Publicación de Broadcast social:**

```sql
create or replace function app.publish_social_event(
    p_event text,
    p_target_user_id uuid,
    p_payload jsonb
)
returns void
language plpgsql
security definer
set search_path = public, app, pg_temp
as $$
declare
    v_topic text;
begin
    if p_event in ('join_request.created', 'join_request.resolved', 'conversation.access_revoked') then
        if p_target_user_id is null then
            raise exception 'El evento requiere destinatario' using errcode = '22023';
        end if;
        if not exists (
            select 1
            from public.perfiles p
            where p.id = p_target_user_id
              and p.eliminado_en is null
        ) then
            raise exception 'Destinatario inexistente' using errcode = '23503';
        end if;
        v_topic := 'notifications:user:' || p_target_user_id::text;
    elsif p_event in ('discover.person_hidden', 'discover.group_unpublished') then
        if p_target_user_id is not null then
            raise exception 'El evento de Descubrir no lleva destinatario' using errcode = '22023';
        end if;
        v_topic := 'discover:global';
    else
        raise exception 'Evento social no permitido' using errcode = '42501';
    end if;

    perform realtime.send(p_payload, p_event, v_topic, true);
end;
$$;

revoke all on function app.publish_social_event(text, uuid, jsonb) from public;
grant execute on function app.publish_social_event(text, uuid, jsonb) to chatly_app;
```

- La función se ejecuta como su propietario (el rol de migraciones), que tiene `INSERT` sobre `realtime.messages` y `BYPASSRLS` (verificado en el proyecto). No necesita políticas `INSERT` en `realtime.messages` para `chatly_app`.
- `realtime.send` captura sus errores con un `WARNING`: un fallo de entrega no revierte la transacción de negocio. El estado persistido sigue siendo la fuente de verdad.
- El payload no incluye correo, mensajes, listas de integrantes ni intereses completos; solo los identificadores y el estado definidos en `realtime-events.md` §5.

**Programación del job:**

```sql
create extension if not exists pg_cron;

select cron.schedule_in_database(
    'expire_join_requests',
    '*/15 * * * *',
    'select app.expire_pending_join_requests();',
    'postgres',
    'chatly_app'
);
```

Verificar la firma de `cron.schedule_in_database` en la versión instalada de `pg_cron` (1.6.4 en el proyecto) y que `chatly_app` pueda ejecutar la función. El job se ejecuta cada 15 minutos y no depende de Render.

### 6.6 Restricciones de modificación de solicitudes

La aplicación no concede `UPDATE` al solicitante para cancelar o editar su solicitud. La transición automática `joined_other_group` se ejecuta mediante la función restringida `app.resolve_pending_request_after_joining_other_group()` y la expiración mediante `app.expire_pending_join_requests()`. El solicitante no puede elegir el estado, motivo ni fecha desde la API.

Para minimizar el riesgo, las columnas actualizables de `solicitudes_union` se conceden de forma explícita y las transiciones automáticas están centralizadas en servicios/funciones específicas. No se concede `DELETE`.

---

## 7. Autorización de Supabase Realtime

Realtime utiliza topics privados. La autorización de Broadcast y Presence se realiza mediante políticas RLS sobre `realtime.messages`; las filas de Postgres Changes se filtran además por las políticas `SELECT` de las tablas fuente.

### 7.1 Topics y permisos

| Topic | Suscripción permitida | Publicación permitida desde navegador |
|---|---|---|
| `conversation:<uuid>` | Usuario verificado con membresía activa en esa conversación | Solo Broadcast `typing`; no puede publicar `read`, eventos de solicitud ni eventos de sistema |
| `presence:user:<uuid>` | El propio usuario; otros usuarios verificados si el perfil objetivo tiene `visibilidad_publica = true` | Solo el propietario del topic, para su propia presencia |
| `notifications:user:<uuid>` | Solo el usuario cuyo UUID aparece en el topic | Ninguna; publica únicamente `app.publish_social_event` ejecutada por `chatly_app` |
| `discover:global` | Usuarios autenticados y verificados | Ninguna; publica únicamente `app.publish_social_event` ejecutada por `chatly_app` |

### 7.2 Políticas de `realtime.messages`

> RLS ya está habilitado en `realtime.messages`. No ejecutar `ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY`.

```sql
-- Recibir Broadcast de escritura solo en una conversación donde el actor sea miembro activo.
create policy realtime_read_typing_conversation on realtime.messages
    for select to authenticated
    using (
        extension = 'broadcast'
        and event = 'typing'
        and realtime.topic() = 'conversation:' || app.topic_conversation_id()::text
        and app.topic_conversation_id() is not null
        and (select app.is_active_member(app.topic_conversation_id()))
    );

-- Enviar únicamente typing y declarar el propio user_id en el payload.
create policy realtime_write_typing_conversation on realtime.messages
    for insert to authenticated
    with check (
        extension = 'broadcast'
        and event = 'typing'
        and app.topic_conversation_id() is not null
        and (select app.is_active_member(app.topic_conversation_id()))
        and payload ->> 'user_id' = (select auth.uid())::text
    );

-- Recibir presencia propia o de perfiles públicos.
create policy realtime_read_user_presence on realtime.messages
    for select to authenticated
    using (
        extension = 'presence'
        and app.topic_user_id() is not null
        and realtime.topic() = 'presence:user:' || app.topic_user_id()::text
        and (select app.is_verified_actor())
        and (select app.can_view_presence(app.topic_user_id()))
    );

-- Publicar presencia únicamente en el topic propio.
create policy realtime_write_own_presence on realtime.messages
    for insert to authenticated
    with check (
        extension = 'presence'
        and app.topic_user_id() is not null
        and realtime.topic() = 'presence:user:' || (select auth.uid())::text
        and app.topic_user_id() = (select auth.uid())
        and (select app.is_verified_actor())
    );

-- Recibir avisos privados únicamente en el topic de la propia cuenta.
create policy realtime_read_own_notifications on realtime.messages
    for select to authenticated
    using (
        extension = 'broadcast'
        and realtime.topic() = 'notifications:user:' || (select auth.uid())::text
        and app.topic_user_id() = (select auth.uid())
        and (select app.is_verified_actor())
    );

-- Recibir invalidaciones mínimas de Descubrir.
create policy realtime_read_discover_invalidations on realtime.messages
    for select to authenticated
    using (
        extension = 'broadcast'
        and realtime.topic() = 'discover:global'
        and (select app.is_verified_actor())
    );
```

No se crean políticas `INSERT` para `notifications:user:<uuid>` ni `discover:global` para `authenticated`. Los eventos `join_request.created`, `join_request.resolved`, `conversation.access_revoked`, `discover.person_hidden` y `discover.group_unpublished` los emite el backend después del commit.

La política de `conversation:<uuid>` autoriza la suscripción y el `typing` del cliente. Los eventos persistidos (mensajes, reacciones, encuestas, votos, conversación y membresías) siguen protegidos por el `SELECT` RLS de sus tablas fuente. No se utiliza Broadcast `read`; las lecturas se persisten en `miembros_conversacion`.

### 7.3 Catálogo de Postgres Changes

Las tablas con cambios persistidos publicados son:

```sql
alter publication supabase_realtime add table
    public.conversaciones,
    public.miembros_conversacion,
    public.mensajes,
    public.reacciones_mensaje,
    public.encuestas,
    public.opciones_encuesta,
    public.votos_encuesta;
```

No se publican:

- `perfiles` ni `contactos_usuario`.
- `categorias_interes`, `intereses`, `intereses_usuario` ni `intereses_conversacion`.
- `solicitudes_union`.
- `versiones_mensaje` ni `registros_auditoria`.

Las solicitudes se notifican mediante Broadcast privado con payload mínimo. Los intereses y recomendaciones se vuelven a consultar mediante API al abrir o refrescar Descubrir.

### 7.4 Topics sociales y payload mínimo

| Evento | Destinatario | Información mínima |
|---|---|---|
| `join_request.created` | Administrador actual del grupo | `request_id`, `conversation_id`, `sent_at` |
| `join_request.resolved` | Solicitante | `request_id`, `conversation_id`, `status`, `reason_code`, `sent_at` |
| `conversation.access_revoked` | Usuario expulsado | `conversation_id`, `reason`, `sent_at` |
| `discover.person_hidden` | Suscriptores de `discover:global` | `user_id`, `sent_at` |
| `discover.group_unpublished` | Suscriptores de `discover:global` | `conversation_id`, `sent_at` |

Los payloads no incluyen correo, contenido de mensajes, lista de integrantes ni intereses completos. El cliente vuelve a consultar los recursos autorizados por API. Los avisos son efímeros; PostgreSQL mantiene el estado definitivo de las solicitudes.

### 7.5 Presencia y escritura

- La presencia se registra por sesión/pestaña en `presence:user:<uuid>`.
- El usuario mantiene el estado online si conserva al menos una sesión activa.
- Otros usuarios solo consultan presencia si el perfil objetivo tiene visibilidad pública; el propietario siempre puede ver su propia presencia.
- No se muestra «última vez visto».
- `typing` solo se emite desde `conversation:<uuid>` por un miembro activo y desaparece tras cinco segundos sin actividad.
- Presencia y escritura no se persisten ni se auditan.

### 7.6 Cacheo de autorización y revocación

La autorización de Broadcast/Presence se calcula al unirse al topic y puede quedar cacheada durante la conexión. Por ello:

1. Al expulsar un integrante, el backend emite `conversation.access_revoked` en su topic privado.
2. El cliente coopera cerrando `conversation:<id>` y limpiando contenido que ya no puede consultar.
3. Las nuevas consultas REST y los nuevos intentos de suscripción se bloquean mediante RLS y reglas de servicio.
4. Se mantiene una duración corta del JWT y se renueva/re-suscribe cuando corresponda.
5. Las pruebas deben incluir un cliente que ignore el aviso; la limitación de una conexión ya abierta queda documentada.

---

## 8. Storage de avatares

- Bucket privado `avatars`.
- Límite: 2 MB; MIME: JPEG, PNG y WebP.
- Ruta obligatoria: `{user_id}/{uuid}.{ext}`.
- El navegador solo puede subir, actualizar o eliminar archivos dentro de su propia carpeta.
- La visualización de avatares ajenos se realiza mediante URLs firmadas de corta duración emitidas por el backend, no abriendo el bucket completo.

```sql
create policy avatars_read_own on storage.objects
    for select to authenticated
    using (
        bucket_id = 'avatars'
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

create policy avatars_insert_own on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'avatars'
        and owner_id = (select auth.uid())
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );

create policy avatars_update_own on storage.objects
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

create policy avatars_delete_own on storage.objects
    for delete to authenticated
    using (
        bucket_id = 'avatars'
        and owner_id = (select auth.uid())
        and (storage.foldername(name))[1] = (select auth.uid())::text
    );
```

El backend valida el objeto subido (tamaño y `content-type`) antes de actualizar `perfiles.ruta_avatar`. Los archivos anteriores se conservan en Storage; el perfil solo apunta al avatar vigente.

---

## 9. Grants y privilegios mínimos

RLS y privilegios SQL son capas distintas. Aplicar primero `REVOKE` y conceder únicamente lo necesario para API, Postgres Changes y Storage.

### 9.1 Privilegios del navegador

```sql
revoke all on all tables in schema public from anon, authenticated;

-- Solo lectura para Postgres Changes de conversaciones y datos de chat autorizados por RLS.
grant select on public.conversaciones,
                public.miembros_conversacion,
                public.mensajes,
                public.reacciones_mensaje,
                public.encuestas,
                public.opciones_encuesta,
                public.votos_encuesta
    to authenticated;
```

No conceder privilegios de tabla a `authenticated` para `perfiles`, `contactos_usuario`, `categorias_interes`, `intereses`, `intereses_usuario`, `intereses_conversacion`, `solicitudes_union`, `versiones_mensaje` ni `registros_auditoria`. Los datos de esas tablas se entregan por API.

**Nota sobre PostgREST:** conceder `SELECT` a `authenticated` en tablas del esquema `public` también puede permitir consultas de solo lectura mediante la Data API si ese esquema está expuesto. RLS sigue filtrando esas filas, pero si el diseño exige que el navegador consuma exclusivamente FastAPI y Realtime, el equipo debe revisar la configuración de esquemas expuestos de Supabase y comprobarla con pruebas reales. No asumir que `GRANT SELECT` sirve solo para Postgres Changes.

### 9.2 Privilegios del backend

El siguiente bloque ilustra los privilegios esperados; verificar los nombres y columnas contra el DDL final antes de aplicarlo:

```sql
-- Perfil y contacto
grant select, insert on public.perfiles to chatly_app;
grant insert on public.contactos_usuario to chatly_app;
grant update (correo_normalizado, actualizado_en) on public.contactos_usuario to chatly_app;

-- Conversaciones y mensajes
grant select, insert on public.conversaciones to chatly_app;
grant select, insert on public.miembros_conversacion to chatly_app;
grant select, insert on public.preferencias_conversacion to chatly_app;
grant select, insert on public.mensajes to chatly_app;
grant select, insert on public.versiones_mensaje to chatly_app;
grant select, insert on public.reacciones_mensaje to chatly_app;
grant select, insert on public.encuestas to chatly_app;
grant select, insert on public.opciones_encuesta to chatly_app;
grant select, insert on public.votos_encuesta to chatly_app;

-- Catálogo social: solo lectura de aplicación
grant select on public.categorias_interes, public.intereses to chatly_app;
grant select on app.perfiles_publicos to chatly_app;
grant execute on function app.buscar_usuario_por_correo(text) to chatly_app;
grant execute on function app.discoverable_group_member_count(uuid) to chatly_app;
grant execute on function app.shared_interests_for_join_request(uuid) to chatly_app;

-- Relaciones de intereses: reemplazo controlado por servicio
grant select, insert, delete on public.intereses_usuario to chatly_app;
grant select, insert, delete on public.intereses_conversacion to chatly_app;

-- Solicitudes: sin DELETE; transiciones mediante columnas concretas
grant select, insert on public.solicitudes_union to chatly_app;
grant update (estado, motivo_resolucion, resuelta_en, resuelta_por, actualizado_en)
    on public.solicitudes_union to chatly_app;

-- Auditoría: solo inserción desde la app
grant insert on public.registros_auditoria to chatly_app;
grant usage, select on sequence public.registros_auditoria_id_seq to chatly_app;

-- Actualizaciones limitadas de perfil
grant update (alias, nombre_visible, ruta_avatar, fecha_nacimiento, genero,
               visibilidad_publica, alias_cambiado_en, actualizado_en)
    on public.perfiles to chatly_app;

-- Actualizaciones limitadas de conversaciones
grant update (nombre, administrador_id, archivada, archivada_en,
               ultimo_mensaje_en, descripcion, es_descubrible, actualizado_en)
    on public.conversaciones to chatly_app;

-- Membresías: el trigger de protección valida el actor y la transición
grant update (rol, estado, salido_en, retirado_por,
               ultimo_mensaje_leido_id, ultimo_leido_en, actualizado_en)
    on public.miembros_conversacion to chatly_app;

grant update (oculta, ocultada_en, actualizado_en)
    on public.preferencias_conversacion to chatly_app;

grant update (contenido, editado_en, conteo_ediciones,
               eliminado_en, eliminado_por, actualizado_en)
    on public.mensajes to chatly_app;

grant update (emoji, eliminado_en, actualizado_en)
    on public.reacciones_mensaje to chatly_app;

grant update (pregunta, estado, cerrada_en, cerrada_por, eliminado_en, actualizado_en)
    on public.encuestas to chatly_app;

grant update (texto, posicion) on public.opciones_encuesta to chatly_app;
grant update (opcion_id, actualizado_en) on public.votos_encuesta to chatly_app;

-- Identidad y transiciones automáticas: sin herencia de authenticated
alter role chatly_app noinherit;
revoke authenticated from chatly_app;
grant execute on function app.publish_social_event(text, uuid, jsonb) to chatly_app;
grant execute on function app.resolve_pending_request_after_joining_other_group(uuid, uuid) to chatly_app;
grant execute on function app.expire_pending_join_requests() to chatly_app;
```

Notas:

- Si el DDL final requiere sincronizar el correo desde Auth, hacerlo mediante una función controlada; no conceder `SELECT` sobre `contactos_usuario`.
- `chatly_app` no hereda `authenticated`. La identidad se resuelve con `app.current_actor_id()` `SECURITY DEFINER`; el rol de migraciones ya tiene `USAGE` sobre `auth` y `EXECUTE` sobre `auth.uid()`. En el proyecto actual la membresía fue otorgada por `postgres` con `admin_option`, por lo que la migración puede revocarla.
- `chatly_app` no tiene `BYPASSRLS`, no es propietario de las tablas y no recibe `DELETE` general.
- `DELETE` queda limitado a las tablas de relación `intereses_usuario` e `intereses_conversacion` para poder reemplazar conjuntos. Los elementos de negocio principales usan borrado lógico.
- No conceder `UPDATE` sobre identificadores, propietario, autor, fecha de creación ni campos de identidad de relaciones.
- El job de `pg_cron` debe invocar solo la función específica de expiración; no recibe permiso para actualizar arbitrariamente cualquier solicitud.
- El propietario de tablas/migraciones ejecuta DDL, catálogo y semillas desde un proceso separado.

---

## 10. Casos negativos obligatorios (pruebas)

### Identidad y privacidad

1. Un usuario no verificado no puede consultar Descubrir, personas recomendadas, grupos descubribles ni conversaciones.
2. Un usuario no puede establecer un `user_id` ajeno en el body para cambiar perfil, intereses o crear una solicitud.
3. El usuario A no puede leer `contactos_usuario` directamente.
4. La búsqueda exacta por correo devuelve nombre, alias y fotografía, pero nunca el correo.
5. Un usuario con `visibilidad_publica = false` no aparece en recomendaciones y sus intereses no se devuelven en su perfil público.
6. A pesar de tener visibilidad desactivada, el usuario puede encontrarse por búsqueda directa y sus resultados básicos no muestran el correo.
7. Un usuario no verificado o externo no puede leer tablas de intereses directamente.
8. Un perfil no verificado no aparece en recomendaciones ni expone su presencia a usuarios verificados.

### Conversaciones y membresías

9. Un usuario ajeno no puede leer una conversación, miembros, mensajes, reacciones o encuestas.
10. Un antiguo miembro solo puede leer mensajes que pertenecen a sus periodos.
11. Un reincorporado no puede leer el intervalo en que estuvo fuera.
12. Un usuario expulsado no puede escribir, reaccionar ni votar.
13. Un integrante que no sea administrador no puede añadir/expulsar miembros ni modificar la información del grupo.
14. El límite de 10 participantes se mantiene incluso con dos incorporaciones concurrentes.
15. Dos transacciones consecutivas con actores distintos no comparten `app.current_user_id`.

### Descubrimiento de personas y grupos

16. Un usuario sin intereses no recibe recomendaciones automáticas de personas ni grupos, pero puede buscar grupos manualmente.
17. Solo se recomienda una persona si el perfil objetivo es público, tiene al menos un interés y hay al menos una coincidencia.
18. Las personas con chat privado existente se excluyen de sugerencias; compartir un grupo no las excluye.
19. La tarjeta de descubrimiento no incluye alias ni un contador/etiqueta de coincidencias; solo intereses compartidos y, cuando esté disponible, presencia.
20. Un usuario externo no puede consultar la lista de miembros ni mensajes de un grupo descubrible.
21. Un grupo privado o archivado no aparece en recomendaciones, búsqueda ni detalle público.
22. Solo el administrador activo puede publicar, despublicar o cambiar intereses/descripción de un grupo.
23. Un grupo descubrible exige descripción de 10–300 caracteres y entre 1 y 5 intereses.
24. Un usuario que ya pertenece o administra un grupo no lo recibe como recomendación.

### Solicitudes de unión

25. Una cuenta no verificada no puede crear una solicitud.
26. Compartir intereses no es requisito para solicitar un grupo descubrible.
27. Un usuario no puede tener más de una solicitud pendiente global; la restricción se mantiene bajo concurrencia.
28. Un usuario no puede cancelar su solicitud ni cambiar su estado desde su cliente.
29. Una solicitud pendiente caduca automáticamente a los 14 días y libera el límite global.
30. Solo un rechazo manual genera siete días de espera para ese mismo grupo.
31. Los rechazos automáticos `group_private`, `group_full` y `joined_other_group` no generan espera de siete días.
32. El administrador solo consulta solicitudes de sus propios grupos y no recibe correo del solicitante.
33. Un administrador que ya no está activo no puede aceptar/rechazar solicitudes.
34. Aceptar solicitud y crear membresía es atómico; nunca se supera el máximo de 10 integrantes.
35. Añadir directamente al solicitante al mismo grupo no crea membresías duplicadas; convierte la solicitud en aceptada.
36. Añadir al solicitante a otro grupo resuelve automáticamente su solicitud pendiente anterior.
37. Al volver el grupo a privado, todas sus solicitudes pendientes se rechazan automáticamente y el grupo deja de aparecer en Descubrir.
38. Las solicitudes resueltas se conservan en la base y auditoría, pero no existe endpoint ni pantalla «Mis solicitudes» histórica.

### Realtime y Storage

39. Un usuario ajeno no puede suscribirse a `conversation:<uuid>`.
40. Un antiguo miembro no puede crear una nueva suscripción a un topic de conversación.
41. Solo el destinatario puede suscribirse a `notifications:user:<uuid>`.
42. Un usuario no puede publicar Broadcast en el topic de notificaciones ni en `discover:global`.
43. Solo el propio usuario puede publicar presencia en `presence:user:<su_uuid>`.
44. Un tercero solo ve presencia si tanto el actor como el perfil objetivo están verificados y el perfil objetivo es público.
45. Un usuario no puede publicar `typing` con el `user_id` de otra persona.
46. Los eventos de solicitudes e invalidaciones no contienen correos, mensajes, listas de miembros ni perfiles completos.
47. Si se pierde un Broadcast, al reconectar la UI recupera el estado mediante endpoints autorizados.
48. Un usuario no puede leer/subir/actualizar/eliminar un avatar en la carpeta de otra persona.
49. Intentar consultar, modificar o eliminar `registros_auditoria` desde la aplicación devuelve permiso denegado.
50. Un usuario no puede ejecutar `app.publish_social_event` ni elegir un evento o topic arbitrario.
51. El job de `pg_cron` no puede modificar solicitudes que no estén vencidas ni cambiar su estado a otro distinto de `expired`.
52. `chatly_app` no conserva privilegios heredados de `authenticated` tras el revoke.

---

## 11. Límites de RLS y responsabilidades del servicio

RLS es una segunda barrera de fila, no sustituye las reglas de dominio ni las transacciones. Las siguientes reglas deben vivir en `backend/services/` y tener pruebas específicas:

- Máximo de 10 integrantes y mínimo de 3 al crear un grupo; se requiere bloqueo de la fila `conversaciones` para evitar carreras.
- Máximo de 10 intereses personales y entre 1 y 5 intereses de grupo; se requiere transacción y bloqueo de la fila propietaria.
- La unicidad y orden de las solicitudes pendientes se garantiza con índice parcial y flujo transaccional.
- Caducidad de 14 días y espera de siete días tras rechazo manual.
- Transiciones permitidas de `solicitudes_union`, motivos de resolución y notificaciones después del commit.
- Confirmar que el grupo sigue descubrible, que hay plaza y que la solicitud sigue pendiente al aceptarla.
- La aceptación de solicitud y la creación de membresía deben ser atómicas.
- Idempotencia de mensajes offline mediante `id_mensaje_cliente`.
- Edición de encuestas solo por el creador antes del primer voto; cierre por administrador solo cuando el creador dejó de pertenecer.
- El rol de servicio debe mantener el contexto del actor y no reutilizar una sesión con el contexto de otra petición.
- El backend filtra DTOs: las recomendaciones de personas no muestran alias/cantidad de coincidencias; los grupos externos no incluyen integrantes ni mensajes; el correo nunca se expone.
- Los agregados e intersecciones necesarios para Descubrir se obtienen mediante funciones de alcance mínimo (`discoverable_group_member_count` y `shared_interests_for_join_request`), nunca mediante lectura irrestricta de las tablas relacionadas.
- Los eventos sociales se publican con `app.publish_social_event(...)` en la misma transacción de la operación. El servicio no acepta topic, evento ni destinatario desde el cliente; el wrapper valida la lista blanca y construye el topic.

---

## 12. Notas de rendimiento y operación

- Índice `ix_miembros_busqueda_politica (conversacion_id, usuario_id, unido_en) INCLUDE (salido_en)` para `app.has_period`.
- Índices de `mensajes (conversacion_id, creado_en DESC, id DESC)` para historial y cursores.
- Índices parciales de `conversaciones` para grupos activos y descubribles.
- Índice parcial único de `solicitudes_union(solicitante_id) WHERE estado = 'pending'` para el límite global.
- Índice de solicitudes pendientes por grupo ordenadas por `(creada_en, id)`.
- Índice de vencimiento para el proceso de expiración y de rechazos manuales para el cooldown de siete días.
- Las funciones auxiliares son `STABLE` cuando corresponde y los predicados simples usan `(select app.current_actor_id())` para reducir evaluaciones por fila.
- Mantener las políticas de Realtime pequeñas: la autorización de topics se calcula al unirse y se cachea durante la conexión.
- Probar políticas RLS con los roles reales y con `EXPLAIN` en consultas de mayor frecuencia antes de cerrar el diseño.
- Ejecutar `supabase db advisors` después de aplicar políticas y grants.

---

### 12.1 Puntos de integración que deben verificarse antes de aplicar SQL

- Los DTO y endpoints usan algunos alias en inglés (`is_public`, `is_discoverable`, `members_count`); las tablas PostgreSQL conservan los nombres en español (`visibilidad_publica`, `es_descubrible`, `miembros_conversacion`). La API realiza ese mapeo.
- `app.group_has_capacity(uuid)`, `app.discoverable_group_member_count(uuid)` y `app.shared_interests_for_join_request(uuid)` son funciones auxiliares propuestas por esta matriz. La primera comprueba capacidad sin exponer membresías; la segunda entrega solo el agregado para el DTO de grupo; la tercera devuelve únicamente la intersección de intereses necesaria para una solicitud pendiente. Deben agregarse a la migración social/RLS correspondiente y probarse con solicitantes, administradores y actores externos.
- `app.resolve_pending_request_after_joining_other_group(uuid, uuid)` y `app.expire_pending_join_requests()` encapsulan transiciones automáticas que no deben poder ejecutarse mediante una actualización arbitraria desde la API. Deben incorporarse a la migración social y restringirse a `chatly_app`.
- Los grants `SELECT` de `authenticated` necesarios para Postgres Changes también pueden permitir consultas por la Data API si `public` está expuesto. Si se requiere impedir el acceso directo vía PostgREST, se debe ajustar la configuración de esquemas expuestos y probar Realtime; RLS por sí sola no diferencia ambos canales de lectura.
- El rol `chatly_app` usa contexto transaccional. La aplicación debe validar el JWT antes de establecer `app.current_user_id`; nunca debe aceptar que el cliente elija ese valor ni reutilizarlo fuera de la transacción.

## 13. Referencias técnicas

- [Supabase — Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security).
- [Supabase — Realtime Authorization](https://supabase.com/docs/guides/realtime/authorization). La autorización de Broadcast/Presence usa RLS sobre `realtime.messages`; las políticas se evalúan al unirse al canal y se cachean durante la conexión.
- [Supabase — Realtime Settings](https://supabase.com/docs/guides/realtime/settings). Para exigir autorización, desactivar el acceso público a canales y usar `private: true` en el cliente.
- [Supabase — Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control).

---

## 14. Exclusiones de autorización de la V1

No se crean políticas, tablas, roles ni endpoints para:

- Amistades o lista de amigos.
- Seguidores/seguidos.
- Solicitudes de contacto o aprobación de conversaciones privadas.
- Bloqueo de usuarios.
- Reportes y moderación avanzada.
- Historial de «Mis solicitudes».
- Acceso público anónimo a perfiles o comunidades.

La relación entre usuarios se limita a conversaciones privadas y membresías de grupos. Las reglas de descubrimiento se aplican mediante intereses y preferencias de visibilidad, sin introducir un sistema social paralelo.
