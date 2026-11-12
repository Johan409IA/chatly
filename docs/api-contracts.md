# Chatly — Contratos de API

> **Estado:** aprobado para implementación; contrato cerrado. La implementación avanza por migraciones y endpoints; no implica que todo esté desplegado.
> **Implementación:** FastAPI integrado en Reflex mediante `api_transformer`. Un solo servidor.
> **Base:** decisiones funcionales Q1–Q179 consolidadas en `docs/chatly.md`, `docs/database-schema.md`, `docs/authorization-matrix.md` y `docs/realtime-events.md`.
> **Regla de oro:** la identidad del actor sale siempre del JWT/cookie de sesión. Ningún cuerpo acepta `user_id` como identidad.

---

## 1. Convenciones

| Tema | Decisión |
|---|---|
| Prefijo | `/api` |
| Formato | JSON UTF-8; `Content-Type: application/json` |
| Fechas | ISO 8601 UTC (`2026-11-01T18:22:31.004Z`) |
| Identificadores | UUID v4 |
| Autenticación | Cookies `HttpOnly` de sesión; en pruebas se acepta `Authorization: Bearer <jwt>` |
| Autorización | Servicio + RLS; el recurso no visible responde **404**, no 403 |
| Errores | Envelope uniforme (sección 2) |
| Idioma | Mensajes en español |
| Idempotencia | `client_message_id` para mensajes; creación de chat directo es idempotente por pareja |
| Paginación | Cursor `(created_at, id)`, sin `OFFSET` |
| CORS | Solo el origen de la aplicación |
| Documentación | Sin OpenAPI/Swagger por ahora: `docs_url`, `redoc_url` y `openapi_url` deshabilitados en todos los entornos |

---

## 2. Formato de error

```json
{
  "error": {
    "code": "alias_taken",
    "message": "Ese alias ya está en uso. Prueba con otro.",
    "details": { "field": "alias" }
  }
}
```

**Estilo del copy:** español, segunda persona, sin jerga técnica y con una acción concreta. `details.field` identifica el campo cuando aplica. Nunca se exponen trazas ni detalles internos. Ejemplos: «La contraseña debe tener al menos 8 caracteres e incluir una mayúscula, una minúscula y un carácter especial.» / «No tienes permiso para añadir a esta persona. Solo el administrador puede hacerlo.»

| Código | HTTP | Cuándo |
|---|---|---|
| `validation_error` | 422 | Pydantic o regla de formato |
| `weak_password` | 422 | No cumple la política de contraseñas |
| `unauthorized` | 401 | Sin sesión o JWT inválido/expirado |
| `email_not_verified` | 403 | Cuenta sin confirmar (Q15) |
| `forbidden` | 403 | Regla de dominio incumplida |
| `not_found` | 404 | Recurso inexistente o no visible |
| `email_already_registered` | 409 | Correo ya usado |
| `alias_taken` | 409 | Alias ocupado (Q57) |
| `alias_change_too_soon` | 422 | Menos de 30 días (Q107) |
| `invalid_credentials` | 401 | Correo o contraseña incorrectos |
| `already_member` | 409 | Integrante activo duplicado (Q86) |
| `conversation_full` | 422 | Más de 10 integrantes (Q8) |
| `not_member` | 403 | Escribe sin membresía activa |
| `read_only_period` | 403 | Antiguo integrante intenta escribir (Q104) |
| `poll_locked` | 422 | Editar opciones tras el primer voto (Q88) |
| `poll_closed` | 422 | Votar o cambiar voto cerrado (Q10) |
| `poll_has_votes` | 422 | Eliminar encuesta con votos (Q93) |
| `message_too_long` | 422 | Más de 4.000 caracteres (Q51) |
| `invalid_avatar` | 422 | Formato, tamaño o ruta inválidos (Q18) |
| `interest_limit_exceeded` | 422 | Más de 10 intereses personales o más de 5 intereses de grupo (Q124, Q121) |
| `pending_join_request_exists` | 409 | El usuario ya tiene una solicitud pendiente global (Q151, Q159) |
| `join_request_cooldown` | 409 | Rechazo manual del mismo grupo hace menos de 7 días (Q129, Q169) |
| `join_request_not_pending` | 409 | La solicitud ya fue resuelta o expiró |
| `group_not_discoverable` | 404 | El grupo no está publicado o dejó de ser descubrible |
| `group_full` | 409 | Al crear una solicitud, el grupo ya alcanzó los 10 integrantes (Q123, Q176). Aceptar una solicitud en un grupo completo responde `200` con la solicitud en `rejected` y motivo `group_full`. |
| `invalid_discovery_profile` | 422 | Descripción o intereses requeridos para publicar un grupo (Q134) |
| `rate_limited` | 429 | Se superó un límite de frecuencia (ver §14) |
| `internal_error` | 500 | Error no controlado |

---

## 3. DTOs comunes

### 3.1 `UserSummary`

```json
{
  "id": "0f8c2a4e-...",
  "alias": "johan_dev",
  "display_name": "Johan Castillón",
  "avatar_url": "https://.../storage/v1/object/sign/avatars/....?token=..."
}
```

### 3.2 `ProfilePublic`

```json
{
  "id": "0f8c2a4e-...",
  "alias": "johan_dev",
  "display_name": "Johan Castillón",
  "avatar_url": "https://...",
  "age": 23,
  "gender": "masculino",
  "is_public": true,
  "interests": [
    { "id": "...", "name": "Programación", "category": "Tecnología" }
  ]
}
```

Reglas: `age` se deriva de `birth_date`; `birth_date` **no** aparece aquí. Visible para usuarios autenticados y verificados (Q109, Q110). `interests` contiene todos los intereses solo cuando `is_public = true`; con visibilidad desactivada se devuelve como lista vacía. El nombre, alias y fotografía siguen disponibles mediante búsqueda directa (Q120, Q139).

### 3.3 `ProfileMe`

```json
{
  "id": "0f8c2a4e-...",
  "email": "johan@example.com",
  "email_verified": true,
  "alias": "johan_dev",
  "display_name": "Johan Castillón",
  "avatar_url": "https://...",
  "birth_date": "2003-04-18",
  "age": 23,
  "gender": "masculino",
  "alias_changed_at": "2026-10-01T12:00:00Z",
  "can_change_alias": true,
  "is_public": true,
  "interests": [
    { "id": "...", "name": "Programación", "category": "Tecnología" }
  ],
  "created_at": "2026-11-01T10:00:00Z"
}
```

### 3.4 `Message`

```json
{
  "id": "b1c2d3e4-...",
  "conversation_id": "6f0f8f7e-...",
  "type": "text",
  "author": { "id": "...", "alias": "johan_dev", "display_name": "Johan Castillón", "avatar_url": "..." },
  "content": "Hola a todos",
  "edited_at": null,
  "deleted": false,
  "reply_to": { "id": "...", "author_alias": "ana", "preview": "Hola" },
  "reactions": [{ "emoji": "👍", "count": 2, "reacted_by_me": true }],
  "read": { "all_read": true, "read_count": 3, "expected_count": 3 },
  "created_at": "2026-11-01T18:22:31.004Z"
}
```

- Si `deleted = true`, `content` es `null` y la UI muestra «Se eliminó un mensaje» (Q85).
- Si `type = "system"`, `author` es `null` y se envía `system_event` + `system_data`.
- Si `type = "poll"`, se incluye `poll` (sección 8).

### 3.5 `Poll`

```json
{
  "id": "9a8b7c6d-...",
  "message_id": "b1c2d3e4-...",
  "question": "¿Qué día hacemos la reunión?",
  "status": "open",
  "created_by": "0f8c2a4e-...",
  "created_at": "2026-11-01T18:20:00Z",
  "closed_at": null,
  "options": [
    { "id": "...", "text": "Lunes", "votes": 2, "voter_ids": ["...", "..."] },
    { "id": "...", "text": "Martes", "votes": 1, "voter_ids": ["..."] }
  ],
  "my_option_id": "...",
  "can_edit": false,
  "can_close": true,
  "can_delete": false
}
```

### 3.6 `ConversationSummary`

```json
{
  "id": "6f0f8f7e-...",
  "type": "group",
  "name": "Equipo de tesis",
  "avatar_url": null,
  "initials": "ET",
  "last_message_at": "2026-11-01T18:22:31Z",
  "last_message_preview": "Johan: Hola a todos",
  "unread_count": 3,
  "is_archived": false,
  "my_role": "admin",
  "members_count": 5,
  "is_discoverable": false,
  "description": null
}
```

---

## 4. Autenticación

### 4.1 `POST /api/auth/register`

Público. Crea la cuenta en Supabase Auth y el perfil en una transacción lógica.

```json
{
  "email": "johan@example.com",
  "password": "********",
  "alias": "johan_dev",
  "display_name": "Johan Castillón",
  "birth_date": "2003-04-18",
  "gender": "masculino",
  "interest_ids": []
}
```

Validaciones:

| Campo | Regla |
|---|---|
| `email` | Formato válido; normalizado a minúsculas; único (Q73) |
| `password` | Mínimo 8 caracteres; al menos una mayúscula, una minúscula y un carácter especial. No se exige número. |
| `alias` | 3–20, empieza por letra, `[a-z0-9_]`, único sin distinguir mayúsculas (Q57) |
| `display_name` | 2–60, obligatorio, no único (Q111) |
| `birth_date` | Fecha válida; edad 18–120 (Q109) |
| `gender` | `femenino` o `masculino` (Q110) |
| `interest_ids` | Opcional; entre 0 y 10 IDs del catálogo. Si se omite o se envía vacío, el usuario termina el registro sin intereses (Q117, Q124, Q178). |

La política de contraseñas se configura en Supabase Auth: longitud mínima 8, requisitos de mayúscula, minúscula y símbolo. No se exige número; si el usuario lo incluye, se acepta. La misma política aplica a la recuperación de contraseña.

Respuesta `201`:

```json
{
  "user_id": "0f8c2a4e-...",
  "status": "verification_required",
  "email": "johan@example.com"
}
```

Errores: `email_already_registered`, `alias_taken`, `validation_error`.

> El registro no inicia sesión de chat: el correo debe confirmarse primero (Q15). La selección de intereses es opcional; también puede completarse después desde el perfil.

### 4.2 `POST /api/auth/login`

```json
{ "email": "johan@example.com", "password": "********" }
```

Respuesta `200`:

```json
{
  "access_token": "eyJ...",
  "expires_in": 600,
  "user": {
    "id": "0f8c2a4e-...",
    "alias": "johan_dev",
    "display_name": "Johan Castillón",
    "email_verified": true
  }
}
```

- Fija `chatly_at` y `chatly_rt` como cookies `HttpOnly`, `Secure`, `SameSite=Lax`.
- `access_token` se devuelve solo para Realtime y se guarda en memoria.
- Si el correo no está confirmado: `403 email_not_verified`.
- Credenciales inválidas: `401 invalid_credentials`.

### 4.3 `POST /api/auth/refresh`

Sin cuerpo. Usa la cookie `chatly_rt`.

```json
{ "access_token": "eyJ...", "expires_in": 600 }
```

Errores: `401 unauthorized`.

### 4.4 `POST /api/auth/logout`

Sin cuerpo. Revoca el refresh en Supabase, borra cookies y responde `204`.

### 4.5 `POST /api/auth/resend-verification`

```json
{ "email": "johan@example.com" }
```

Respuesta `202` siempre (no revela si el correo existe). Límite: 3 reenvíos cada 15 minutos por IP y correo (ver §14).

### 4.6 `POST /api/auth/forgot-password`

```json
{ "email": "johan@example.com" }
```

Respuesta `202` siempre. El correo lleva el enlace de recuperación de Supabase.

### 4.7 `POST /api/auth/reset-password`

```json
{ "token": "token-de-recuperacion", "password": "********" }
```

Respuesta `204`. Se aplica la misma política de contraseñas del registro. Errores: `401 unauthorized`, `422 weak_password`, `validation_error`.

---

## 5. Perfil propio

### 5.1 `GET /api/me`

Devuelve `ProfileMe`.

### 5.2 `PATCH /api/me`

Actualiza campos permitidos. Todos opcionales, pero al menos uno.

```json
{
  "display_name": "Johan C.",
  "alias": "johan_c",
  "birth_date": "2003-04-18",
  "gender": "masculino",
  "is_public": true
}
```

| Campo | Regla |
|---|---|
| `display_name` | 2–60 (Q111) |
| `alias` | 3–20, formato de Q57, único, 1 cambio/30 días (Q107) |
| `birth_date` | Edad 18–120 (Q109) |
| `gender` | `femenino` o `masculino` (Q110) |
| `is_public` | Booleano; valor inicial `true`. Controla recomendaciones de personas y visibilidad de intereses, no la publicación de grupos (Q116, Q139). |

- Cada cambio se audita (Q43).
- Respuesta `200` con `ProfileMe`.
- Para reemplazar los intereses se utiliza `PUT /api/me/interests` (sección 16).
- Errores: `alias_taken`, `alias_change_too_soon`, `validation_error`.

### 5.3 `POST /api/me/avatar`

Finaliza una subida directa a Storage.

```json
{ "object_path": "0f8c2a4e-.../1b2c3d4e-....webp" }
```

Flujo:

1. El navegador sube el archivo a `avatars/{user_id}/{uuid}.{ext}` con `supabase-js` y el JWT del usuario.
2. El bucket aplica límite de 2 MB y tipos JPEG/PNG/WebP (Q18).
3. El backend hace `HEAD` del objeto, verifica tipo y tamaño, y actualiza `perfiles.ruta_avatar`.
4. El archivo anterior se conserva en Storage; solo cambia la referencia vigente (Q80).
5. Respuesta `200` con `{ "avatar_url": "..." }` (URL firmada con **10 minutos** de vigencia).

Errores: `invalid_avatar`, `not_found`.

### 5.4 `DELETE /api/me/avatar`

Elimina la referencia vigente y vuelve al avatar predeterminado. El archivo se conserva (Q80, Q18). Respuesta `204`.

### 5.5 `GET /api/profiles/{user_id}`

Devuelve `ProfilePublic`. No incluye correo ni fecha de nacimiento. Si `is_public = false`, mantiene nombre, alias y fotografía, pero no revela intereses. `404` si no existe o está borrado.

---

## 6. Búsqueda de usuarios

### 6.1 `GET /api/users/search`

Parámetros mutuamente excluyentes:

| Parámetro | Regla |
|---|---|
| `q` | Búsqueda parcial por alias, mínimo **2** caracteres, sin distinguir mayúsculas (Q112) |
| `email` | Coincidencia **exacta**, normalizada; nunca se devuelve el correo (Q7, Q73) |

- Excluye al propio usuario (Q112).
- Requiere usuario autenticado y verificado.
- La búsqueda directa sigue disponible aunque el usuario encontrado tenga `is_public = false`; esta preferencia solo controla las recomendaciones y la visibilidad de sus intereses (Q120, Q139).
- Devuelve como máximo **20** resultados (confirmado).

Respuesta `200`:

```json
{
  "results": [
    { "id": "...", "alias": "ana_ml", "display_name": "Ana Martínez", "avatar_url": "..." }
  ]
}
```

Errores: `validation_error` si faltan ambos o se envían los dos.

---

## 7. Conversaciones y grupos

### 7.1 `GET /api/conversations`

Lista ordenada por `last_message_at desc` (Q95). Incluye conversaciones ocultas solo si `?include_hidden=true`.

Respuesta:

```json
{
  "items": [ /* ConversationSummary */ ],
  "total_unread": 7
}
```

### 7.2 `POST /api/conversations/direct`

Prepara o abre el chat con otra persona. No crea por sí solo una conversación persistente.

```json
{ "recipient_id": "0f8c2a4e-..." }
```

- Si ya existe la conversación privada de la pareja, devuelve `200` con la conversación existente (Q20).
- Si todavía no existe, devuelve `200` con un chat temporal (`conversation_id: null`, `is_temporary: true`) y los datos básicos del destinatario. No se inserta ninguna fila en `conversaciones` ni `miembros_conversacion`.
- La conversación y las membresías se crean de forma atómica cuando se envía el primer mensaje mediante `POST /api/messages/direct` (Q146).
- El actor siempre se obtiene de la sesión; `recipient_id` identifica al destinatario, no al actor.
- Errores: `not_found` (destinatario inexistente), `forbidden` (destinatario no verificado) y `validation_error` (el actor se envía a sí mismo como destinatario).

### 7.2.1 `POST /api/messages/direct`

Envía el primer mensaje a una persona con la que todavía no existe una conversación persistida, o reutiliza la conversación privada si ya existe.

```json
{
  "recipient_id": "0f8c2a4e-...",
  "content": "Hola, vi que compartimos interés en programación.",
  "client_message_id": "3f2a1b0c-..."
}
```

- `recipient_id` es el destinatario; el actor se obtiene del JWT/cookie.
- `content`: 1–4.000 caracteres (Q51).
- `client_message_id`: UUID para evitar duplicados ante reintentos (Q40).
- La operación busca una conversación única para la pareja; si no existe, crea la conversación directa, las dos membresías y el primer mensaje dentro de una misma transacción (Q20, Q146).
- Si ya existe la conversación, reutiliza su ID y añade el mensaje.
- Respuesta `201` cuando se crea la conversación; `200` cuando se reutiliza una existente o se devuelve un reintento idempotente.
- Errores: `not_found`, `forbidden`, `message_too_long`, `validation_error`.

### 7.3 `POST /api/conversations/groups`

```json
{
  "name": "Equipo de tesis",
  "member_ids": ["...", "..."]
}
```

| Regla | Valor |
|---|---|
| Nombre | 3–40, se recorta (Q87) |
| Mínimo al crear | 3 integrantes incluyendo al creador (Q89) |
| Máximo | 10 integrantes incluyendo al creador (Q8) |
| Administrador | El creador (Q8) |

Los grupos se crean privados por defecto (`is_discoverable = false`). La descripción y los intereses para descubrimiento se configuran después desde el endpoint de descubribilidad (sección 16).

Respuesta `201` con el detalle de la conversación.
Errores: `validation_error`, `conversation_full`, `not_found`.

### 7.4 `GET /api/conversations/{id}`

Detalle con integrantes, roles, administrador actual, estado de archivo y mi membresía.

```json
{
  "id": "...",
  "type": "group",
  "name": "Equipo de tesis",
  "admin_id": "...",
  "is_archived": false,
  "is_discoverable": true,
  "description": "Espacio para aprender y compartir conocimientos.",
  "interests": [
    { "id": "...", "name": "Programación", "category": "Tecnología" }
  ],
  "created_at": "...",
  "members": [
    { "user": { /* UserSummary */ }, "role": "admin", "joined_at": "...", "active": true },
    { "user": { /* UserSummary */ }, "role": "member", "joined_at": "...", "active": true }
  ],
  "my_membership": { "role": "member", "active": true, "joined_at": "..." }
}
```

### 7.5 `PATCH /api/conversations/{id}`

```json
{ "name": "Nuevo nombre" }
```

Solo el administrador activo (Q46). Reglas de nombre de Q87. Respuesta `200` con el detalle.

### 7.6 `POST /api/conversations/{id}/members`

```json
{ "user_id": "..." }
```

Solo administrador activo (Q81). Respuesta `201` con la membresía creada. Además, dentro de la misma transacción:

- Si existe una solicitud pendiente del usuario para **este mismo grupo**, se marca como aceptada y se crea una sola membresía (Q144).
- Si existe una solicitud pendiente para **otro grupo**, se rechaza automáticamente para conservar el límite global de una solicitud pendiente (Q166).
- Si el grupo alcanza diez integrantes, las demás solicitudes pendientes para ese grupo se rechazan automáticamente por grupo completo (Q130).

Errores: `already_member` (Q86), `conversation_full` (Q8), `not_found`.

### 7.7 `DELETE /api/conversations/{id}/members/{user_id}`

Solo administrador activo (Q35). Cierra la membresía con `status = "removed"`. Respuesta `204`.
Errores: `forbidden`, `not_found`.

> El administrador no puede expulsarse a sí mismo con este endpoint: para salir usa `POST /api/conversations/{id}/leave`, que aplica la sucesión automática (Q21, Q47).

### 7.8 `POST /api/conversations/{id}/leave`

```json
{ "mode": "keep_history" }
```

| `mode` | Efecto |
|---|---|
| `keep_history` | Cierra la membresía y conserva el historial en solo lectura (Q21) |
| `hide` | Cierra la membresía y oculta la conversación para el usuario (Q30) |

- Si el que sale es administrador, la administración pasa al integrante activo con mayor antigüedad (Q21, Q47).
- Si es el último integrante, la conversación se archiva y se cierran las encuestas abiertas (Q45, Q63).
- Respuesta `200`:

```json
{ "archived": false, "new_admin_id": "..." }
```

Si la conversación se archiva, `new_admin_id` es `null`.

### 7.9 `PUT /api/conversations/{id}/preferences`

```json
{ "hidden": true }
```

Preferencia individual (Q59, Q68). Respuesta `200`.

### 7.10 `POST /api/conversations/{id}/read`

```json
{ "message_id": "..." }
```

Marca lectura solo si la conversación está abierta y la pestaña visible (Q60). Actualiza `last_read_message_id` y `last_read_at` de la membresía activa. Respuesta `200`:

```json
{ "last_read_message_id": "...", "last_read_at": "2026-11-01T18:25:00Z" }
```

---

## 8. Mensajes, reacciones y encuestas

### 8.1 `GET /api/conversations/{id}/messages`

| Parámetro | Regla |
|---|---|
| `limit` | Por defecto 50, máximo 50 (Q94) |
| `before_created_at` | Cursor; junto con `before_id` |
| `before_id` | Cursor; junto con `before_created_at` |

Respuesta:

```json
{
  "items": [ /* Message, ordenados de más antiguo a más reciente */ ],
  "next_cursor": { "created_at": "2026-11-01T18:00:00Z", "id": "..." }
}
```

- Sin cursor: últimos 50.
- Con cursor: 30 anteriores por página.
- Un antiguo integrante solo recibe los mensajes de sus periodos (Q104).

### 8.2 `POST /api/conversations/{id}/messages`

```json
{
  "content": "Hola a todos",
  "client_message_id": "3f2a1b0c-...",
  "reply_to_message_id": null
}
```

| Campo | Regla |
|---|---|
| `content` | 1–4.000 caracteres, saltos de línea permitidos (Q51) |
| `client_message_id` | UUID generado en el dispositivo; idempotencia offline (Q40) |
| `reply_to_message_id` | Debe pertenecer a la misma conversación (Q75) |

- Requiere membresía activa y correo verificado.
- Respuesta `201`:

```json
{ "message": { /* Message */ }, "idempotent_replay": false }
```

- Si `client_message_id` ya existe, `200` con el mensaje existente e `"idempotent_replay": true`.
- Errores: `not_member`, `read_only_period`, `message_too_long`, `validation_error`.

### 8.3 `PATCH /api/messages/{id}`

```json
{ "content": "Texto corregido" }
```

- Solo el autor, mientras sea miembro activo, sin límite de tiempo (Q11, Q84).
- Guarda la versión anterior en `message_versions` y actualiza `edited_at` (Q33).
- Respuesta `200` con `Message`.
- Errores: `forbidden`, `message_too_long`.

### 8.4 `DELETE /api/messages/{id}`

Borrado lógico. Solo el autor activo (Q11). Respuesta `204`. El contenido no se devuelve en consultas normales (Q85).

### 8.5 `PUT /api/messages/{id}/reaction`

```json
{ "emoji": "👍" }
```

- Emojis permitidos: `👍 ❤️ 😂 😮 😢 🙏 ✅` (Q12).
- Una reacción vigente por usuario y mensaje; cambiar reemplaza (Q12, Q70).
- Requiere membresía activa y mensaje visible.
- Respuesta `200` con el resumen de reacciones del mensaje.

### 8.6 `DELETE /api/messages/{id}/reaction`

Quita la reacción propia (borrado lógico). Respuesta `204`.

### 8.7 `POST /api/conversations/{id}/polls`

```json
{
  "question": "¿Qué día hacemos la reunión?",
  "options": ["Lunes", "Martes", "Miércoles"]
}
```

| Regla | Valor |
|---|---|
| Pregunta | 5–200 caracteres (Q88) |
| Opciones | 2–5 (Q88) |
| Texto de opción | 1–80 caracteres (Q88) |
| Duplicados | Prohibidos ignorando mayúsculas y espacios (Q88) |

Crea un mensaje `type = poll` y la encuesta en la misma transacción (Q65). Respuesta `201`:

```json
{ "message": { /* Message */ }, "poll": { /* Poll */ } }
```

### 8.8 `GET /api/polls/{id}`

Devuelve `Poll` con opciones, conteos y votantes (Q9).

### 8.9 `PATCH /api/polls/{id}`

```json
{ "question": "Nueva pregunta", "options": ["A", "B"] }
```

Solo el creador y solo antes del primer voto (Q92). Respuesta `200` con `Poll`.
Errores: `poll_locked`, `forbidden`.

### 8.10 `POST /api/polls/{id}/close`

Cierra definitivamente (Q10). Puede cerrarla:

- el creador, o
- el administrador activo, si el creador ya no pertenece al grupo (Q24, Q108).

Respuesta `200` con `Poll`. Errores: `poll_closed`, `forbidden`.

### 8.11 `DELETE /api/polls/{id}`

Borrado lógico solo si no tiene votos (Q93). Respuesta `204`. Errores: `poll_has_votes`, `forbidden`.

### 8.12 `PUT /api/polls/{id}/vote`

```json
{ "option_id": "..." }
```

- Un voto vigente por usuario y encuesta; cambiar actualiza la fila (Q23, Q69).
- Requiere membresía activa y encuesta abierta.
- Respuesta `200` con `Poll`.
- Errores: `poll_closed`, `not_member`, `validation_error`.

---

## 9. Realtime ingest

### 9.1 `POST /api/realtime/ingest`

Ver `docs/realtime-events.md` §5.

```json
{
  "conversation_id": "...",
  "kind": "message",
  "event": "INSERT",
  "entity_id": "...",
  "sent_at": "2026-11-01T18:22:31.004Z"
}
```

| Respuesta | Significado |
|---|---|
| `202` `{ "accepted": true }` | Evento releído y aplicado al estado |
| `204` | No visible, duplicado o irrelevante |
| `401` | Sesión inválida |
| `403` | Sin acceso a la conversación |
| `422` | Payload inválido |

Nunca acepta contenido del mensaje: solo identificadores.

---

## 10. Salud

### 10.1 `GET /api/health`

Público.

```json
{ "status": "ok", "db": "ok", "version": "0.1.0" }
```

`503` si la base no responde.

---

## 11. Resumen de validaciones

| Regla | Valor | Origen |
|---|---|---|
| Alias | 3–20, `^[a-z][a-z0-9_]{2,19}$`, único | Q57 |
| Cambio de alias | 1 cada 30 días | Q107 |
| Nombre visible | 2–60, no único | Q111 |
| Edad | 18–120, derivada | Q109 |
| Género | `femenino`, `masculino` | Q110 |
| Búsqueda por alias | mínimo 2 caracteres, sin el propio usuario | Q112 |
| Nombre de grupo | 3–40 | Q87 |
| Integrantes al crear | 3–10 | Q8, Q89 |
| Máximo de integrantes | 10 | Q8 |
| Mensaje | 1–4.000 caracteres | Q51 |
| Pregunta de encuesta | 5–200 | Q88 |
| Opciones | 2–5, texto 1–80, sin duplicados | Q88 |
| Reacciones | 7 emojis, una vigente | Q12 |
| Avatar | JPEG/PNG/WebP, 2 MB | Q18 |
| Paginación de mensajes | 50 inicial, 30 anteriores | Q94 |
| Intereses personales | 0–10; vacío permitido | Q117, Q124 |
| Intereses de grupo descubrible | 1–5 | Q121, Q134, Q178 |
| Descripción de grupo descubrible | 10–300 caracteres | Q134 |
| Integrantes de grupo | máximo 10; incluye creador | Q8 |
| Solicitud pendiente | máximo 1 global por usuario | Q151, Q159 |
| Caducidad de solicitud | 14 días | Q160 |
| Espera tras rechazo manual | 7 días para el mismo grupo | Q129, Q147, Q169 |

---

## 12. Códigos de estado por operación

| Operación | Éxito | Errores esperables |
|---|---|---|
| Registro | 201 | 409, 422 |
| Login | 200 | 401, 403 |
| Refresh | 200 | 401 |
| Logout | 204 | 401 |
| Perfil propio | 200 | 401, 403 |
| Actualizar perfil | 200 | 401, 409, 422 |
| Buscar usuarios | 200 | 401, 403, 422 |
| Listar conversaciones | 200 | 401, 403 |
| Preparar chat directo | 200 | 401, 403, 404 |
| Enviar primer mensaje directo | 200/201 | 401, 403, 404, 422 |
| Crear grupo | 201 | 401, 403, 422 |
| Detalle de conversación | 200 | 401, 404 |
| Añadir/expulsar | 201/204 | 401, 403, 404, 409, 422 |
| Salir | 200 | 401, 403, 404 |
| Leer mensajes | 200 | 401, 404 |
| Enviar mensaje | 201 | 401, 403, 404, 422 |
| Editar/eliminar mensaje | 200/204 | 401, 403, 404, 422 |
| Reaccionar | 200/204 | 401, 403, 404, 422 |
| Crear encuesta | 201 | 401, 403, 404, 422 |
| Votar | 200 | 401, 403, 404, 422 |
| Cerrar/eliminar encuesta | 200/204 | 401, 403, 404, 422 |
| Catálogo de intereses (público) | 200 | — |
| Actualizar intereses propios | 200 | 401, 403, 422 |
| Recomendaciones de personas/grupos | 200 | 401, 403, 422, 429 |
| Buscar/detallar grupo descubrible | 200 | 401, 403, 404, 422, 429 |
| Configurar descubribilidad | 200 | 401, 403, 404, 422 |
| Crear solicitud de unión | 201 | 401, 403, 404, 409, 422, 429 |
| Consultar solicitud pendiente propia | 200 | 401, 403 |
| Listar solicitudes del grupo | 200 | 401, 403, 404 |
| Aceptar/rechazar solicitud | 200 | 401, 403, 404, 409 |

---

## 13. Seguridad del contrato

1. **Identidad:** el actor se deriva del JWT validado. Cualquier `user_id` en un cuerpo se rechaza o se ignora según el caso; nunca se usa para autorizar.
2. **Recursos ajenos:** se responde `404`, no `403`, para no revelar existencia.
3. **Correo:** nunca se devuelve en búsquedas ni en perfiles públicos.
4. **Cookies:** `HttpOnly`, `Secure`, `SameSite=Lax`. Las mutaciones requieren JSON y mismo origen.
5. **Idempotencia:** los mensajes offline usan `client_message_id`; el reenvío no duplica.
6. **Logs:** sin tokens, cookies, contraseñas ni contenido de mensajes.
7. **Errores:** mensajes en español, sin trazas ni detalles internos.
8. **Límites de tamaño:** validados en Pydantic y en `check` de la base.
9. **Descubrimiento:** solo usuarios autenticados y verificados acceden a personas y grupos descubribles. El catálogo de intereses es público y no expone datos personales. Las tarjetas de personas no exponen alias ni cantidad de coincidencias; solo intereses compartidos.
10. **Privacidad social:** `is_public` controla recomendaciones de personas e intereses del perfil; no cambia la visibilidad de los grupos que administra. `is_discoverable` es independiente y solo lo modifica el administrador del grupo.
11. **Solicitudes:** el actor siempre se deriva de la sesión. El `user_id` del solicitante nunca se acepta desde el cuerpo; la solicitud se atribuye al usuario autenticado.
12. **Datos de grupos:** ningún endpoint de descubrimiento devuelve lista de integrantes ni mensajes de un grupo a usuarios externos.

---

## 14. Límites de frecuencia

Se aplican en la capa HTTP (FastAPI) y en memoria del proceso. Al ser una sola instancia y sin Redis, los contadores se reinician al reiniciar el servicio; es aceptable para la demostración y se documenta como limitación.

| Operación | Límite | Clave |
|---|---|---|
| Login | 10 intentos / 15 min | IP + correo normalizado |
| Reenvío de verificación | 3 / 15 min | IP + correo |
| Recuperación de contraseña | 3 / 15 min | IP + correo |
| Búsqueda de usuarios | 30 / min | usuario autenticado |
| Descubrir personas, grupos, búsqueda y detalle | 30 / min | usuario verificado |
| Crear solicitud de unión | 10 / min | usuario verificado |
| Consultar la solicitud pendiente propia | 60 / min | usuario verificado |
| Envío de mensajes | 30 / min | usuario autenticado |
| Reacciones | 60 / min | usuario autenticado |

- Al exceder: `429 rate_limited` con cabecera `Retry-After` en segundos.
- Los límites de Descubrir evitan recorrer toda la población pública verificada mediante paginación. Se aplican por usuario después de verificar el JWT. El catálogo de intereses es público y cacheable; no necesita límite por usuario.
- Los límites por usuario se aplican después de verificar el JWT; los de autenticación, antes.
- Detrás de Render, la IP se toma de `X-Forwarded-For` con `trusted_proxy_hops = 1`. No se confía en la cabecera si no hay proxy.
- Supabase Auth mantiene sus propios límites; los de la aplicación son complementarios.
- Los valores son configurables mediante variables `RATE_LIMIT_*` sin cambiar código.

> La recuperación de contraseña no estaba en la lista original de la decisión. Se le aplica el mismo límite que al reenvío de verificación (3/15 min) por simetría; queda pendiente tu confirmación si prefieres otro valor.

---

## 15. Decisiones cerradas

1. **Contraseñas:** mínimo 8 caracteres, al menos una mayúscula, una minúscula y un carácter especial; número opcional. Se configura en Supabase Auth y aplica también a la recuperación.
2. **Límites de frecuencia:** moderados, según la tabla de la sección 14.
3. **URLs firmadas de avatares:** 10 minutos.
4. **OpenAPI/Swagger:** sin documentación de API por ahora; `docs_url`, `redoc_url` y `openapi_url` deshabilitados en todos los entornos.
5. **Mensajes de error:** claros y directos, en segunda persona, con acción concreta y `details.field` cuando aplique.
6. **Búsqueda de usuarios:** máximo 20 resultados.


---

## 16. Descubrimiento social, intereses y solicitudes de unión (Q113–Q179)

Esta sección extiende los contratos existentes sin crear un segundo tipo de conversación ni un sistema de amistades. Las personas se conectan mediante chats privados y las comunidades reutilizan las conversaciones grupales existentes.

### 16.1 DTOs sociales

#### `InterestCategory`

```json
{
  "id": "...",
  "name": "Tecnología",
  "interests": [
    { "id": "...", "name": "Programación" },
    { "id": "...", "name": "Inteligencia artificial" }
  ]
}
```

Las categorías sirven para organizar la selección; el usuario selecciona intereses concretos, no categorías completas (Q163, Q178).

#### `PersonRecommendation`

```json
{
  "id": "...",
  "display_name": "Ana Martínez",
  "avatar_url": "https://...",
  "shared_interests": [
    { "id": "...", "name": "Programación" },
    { "id": "...", "name": "Python" }
  ]
}
```

La tarjeta no muestra `alias` ni un contador o etiqueta de cantidad de coincidencias; muestra únicamente los intereses compartidos. El estado online no viene en esta respuesta: el cliente lo calcula suscribiéndose a `presence:user:<id>` cuando el perfil es público (Q119, Q173; realtime-events §3.2 y §6). Al seleccionar la tarjeta, el cliente abre o reutiliza el chat directo. La conversación se persiste al enviar el primer mensaje (Q146).

#### `DiscoverableGroupSummary`

```json
{
  "id": "...",
  "name": "Comunidad de programación",
  "description": "Espacio para aprender y compartir conocimientos.",
  "interests": [
    { "id": "...", "name": "Programación" },
    { "id": "...", "name": "Python" }
  ],
  "members_count": 8,
  "available_places": 2,
  "is_full": false,
  "my_request_status": null,
  "can_request_to_join": true
}
```

No incluye lista de integrantes, perfiles de integrantes ni mensajes (Q132). Un grupo completo sigue apareciendo, con `is_full = true` y `can_request_to_join = false` (Q123). `my_request_status` se refiere únicamente a este grupo; una solicitud pendiente en otro grupo no aparece aquí, pero deshabilita `can_request_to_join` en todos (Q159). El servidor evalúa esa condición una vez por consulta y el cliente puede contrastarla con `GET /api/me/join-request`.

#### `JoinRequest`

```json
{
  "id": "...",
  "group_id": "...",
  "group_name": "Comunidad de programación",
  "status": "pending",
  "created_at": "2026-11-01T18:00:00Z",
  "expires_at": "2026-11-15T18:00:00Z",
  "resolved_at": null
}
```

Estados permitidos: `pending`, `accepted`, `rejected` y `expired`. No existe `cancelled`: el solicitante no puede cancelar (Q122, Q160). No hay DTO ni endpoint para consultar un historial «Mis solicitudes» (Q177).

#### `AdminJoinRequestItem`

```json
{
  "id": "...",
  "group_id": "...",
  "requester": {
    "id": "...",
    "display_name": "Ana Martínez",
    "alias": "ana_ml",
    "avatar_url": "https://..."
  },
  "shared_interests": [
    { "id": "...", "name": "Programación" }
  ],
  "created_at": "2026-11-01T18:00:00Z",
  "expires_at": "2026-11-15T18:00:00Z"
}
```

Es el elemento de la bandeja del administrador. Incluye solo fotografía, nombre visible, alias, intereses compartidos con el grupo y fecha de solicitud (Q157); nunca el correo. `shared_interests` se obtiene con `app.shared_interests_for_join_request(uuid)` y no vuelve público el perfil del solicitante.

### 16.2 Catálogo y selección de intereses

#### `GET /api/interests`

Devuelve las categorías activas y sus intereses, ordenados por el campo de orden del catálogo. Es **público**: el registro lo consume antes de que exista sesión, porque el login está bloqueado hasta confirmar el correo (Q15). Se sirve con `Cache-Control: public, max-age=3600`. Es el único endpoint social público; personas, grupos, perfiles y solicitudes siguen exigiendo usuario verificado (Q128).

Respuesta `200`: lista de `InterestCategory`.

El catálogo es predefinido y se mantiene mediante los datos de la aplicación; los usuarios no pueden crear intereses personalizados ni editar categorías (Q149). Durante el registro puede enviarse `interest_ids` opcional; posteriormente se reemplazan con el endpoint siguiente.

#### `PUT /api/me/interests`

Reemplaza la selección completa de intereses del usuario autenticado.

```json
{
  "interest_ids": ["uuid-interes-1", "uuid-interes-2"]
}
```

- Se permiten entre 0 y 10 intereses. El arreglo vacío equivale a omitir la selección (Q117, Q124).
- Solo se aceptan IDs activos que existan en el catálogo.
- No se aceptan categorías como selección.
- Se audita el cambio.
- Las recomendaciones se recalculan al abrir Descubrir o actualizar resultados, no en cada modificación de la selección (Q164).

Respuesta `200`: `ProfileMe` actualizado.
Errores: `validation_error`, `interest_limit_exceeded`.

### 16.3 Visibilidad del perfil

`PATCH /api/me` acepta el campo `is_public`.

- El valor predeterminado es `true` (Q116).
- Con `true`, la persona puede aparecer en recomendaciones si tiene al menos un interés y se cumplen las demás condiciones; sus intereses se muestran en el perfil público (Q116, Q138).
- Con `false`, desaparece de las recomendaciones y sus intereses dejan de mostrarse en el perfil. Nombre, fotografía y alias siguen disponibles por búsqueda directa (Q120, Q139).
- La visibilidad personal no modifica la configuración de descubribilidad de los grupos administrados (Q165).

### 16.4 Recomendaciones de personas

#### `GET /api/discover/people`

Parámetros:

| Parámetro | Regla |
|---|---|
| `limit` | 20 por defecto y máximo 20 (Q148) |
| `cursor` | Cursor opaco y firmado (HMAC con el secreto de la aplicación) que contiene la semilla y la última clave; el cliente no lo interpreta ni lo modifica |

Respuesta `200`:

```json
{
  "items": [ /* PersonRecommendation */ ],
  "next_cursor": "opaque-cursor-or-null"
}
```

Reglas de selección:

1. El solicitante debe estar autenticado y verificado.
2. Solo aparecen otros usuarios con visibilidad pública activa y al menos un interés seleccionado.
3. Se requiere al menos un interés compartido; no es necesario que coincidan todos.
4. Se excluyen usuarios con los que ya existe una conversación privada. Compartir un grupo no es motivo de exclusión (Q126, Q167).
5. Se ordena por cantidad de intereses compartidos, de mayor a menor; los empates se ordenan por `md5(seed || ':' || id)` ascendente. La `seed` la genera el servidor en la primera página y se renueva al actualizar los resultados (Q118, Q125).
6. El cursor contiene `seed`, `after_count`, `after_hash` y `after_id`; la página siguiente reutiliza la misma semilla y no vuelve a aleatorizar el orden. Un cursor alterado se rechaza con `validation_error` (Q125, Q148).
7. Si el solicitante no tiene intereses, devuelve `items: []` y `next_cursor: null` sin bloquear el resto de Descubrir (Q140).
8. Si un cambio de intereses elimina la coincidencia, la persona deja de aparecer al recalcular (Q172).

No se incorpora un endpoint para descartar, seguir o enviar una solicitud de contacto a una persona. Al pulsar una tarjeta se abre el chat existente o se prepara uno temporal; la conversación nueva se crea al enviar el primer mensaje.

### 16.5 Recomendaciones, búsqueda y detalle de grupos

#### `GET /api/discover/groups`

Parámetros `limit` (20 por defecto, máximo 20) y `cursor` (opaco y firmado).

Devuelve `DiscoverableGroupSummary` ordenados por número de intereses coincidentes y con empates por `md5(seed || ':' || id)`, manteniendo el orden al paginar con el mismo esquema de cursor firmado que las personas (Q133, Q155, Q148).

Reglas:

- Solo grupos activos y descubribles.
- Al menos un interés coincidente para aparecer en recomendaciones.
- No recomendar grupos donde el usuario ya tenga una membresía activa ni grupos que administre (Q168).
- Los grupos completos siguen apareciendo, pero no aceptan solicitudes (Q123).
- Sin intereses personales, no se devuelven recomendaciones automáticas de grupos; el usuario conserva la búsqueda manual por nombre (Q140).
- Los cambios de intereses del usuario o del grupo se reflejan al abrir o actualizar Descubrir (Q164, Q174).

#### `GET /api/discover/groups/search?q=...`

Parámetros:

| Parámetro | Regla |
|---|---|
| `q` | Texto no vacío; búsqueda parcial por nombre. Las decisiones funcionales no fijaron una longitud mínima para esta búsqueda. |
| `limit` | 20 por defecto y máximo 20 |
| `cursor` | Cursor opaco para cargar la siguiente página |

Búsqueda parcial por nombre y resultados progresivos.
- Devuelve únicamente grupos descubribles; no requiere coincidencia de intereses y funciona aunque el usuario no haya seleccionado intereses (Q136, Q140, Q156).
- No expone grupos privados ni la lista de integrantes o mensajes.
- La búsqueda no se realiza por alias del administrador.

#### `GET /api/discover/groups/{group_id}`

Devuelve el detalle público del grupo: nombre, descripción, intereses, cantidad de integrantes, plazas disponibles, estado de grupo completo y estado de solicitud del actor si existe. No devuelve la lista de integrantes ni mensajes (Q132, Q135).

Solo accesible para usuarios autenticados y verificados y mientras el grupo sea descubrible. Si deja de serlo, responde `404`.

### 16.6 Configuración de descubribilidad de un grupo

#### `PUT /api/conversations/{conversation_id}/discoverability`

Solo el administrador actual de una conversación de tipo `group` puede utilizarlo (Q142).

Para publicar o actualizar:

```json
{
  "is_discoverable": true,
  "description": "Espacio para aprender programación y compartir conocimientos.",
  "interest_ids": ["uuid-interes-1", "uuid-interes-2"]
}
```

- `description`: obligatorio al publicar; entre 10 y 300 caracteres (Q134).
- `interest_ids`: entre 1 y 5 IDs del catálogo (Q121, Q174).
- La visibilidad se activa solo si ambas condiciones se cumplen.
- Los grupos son privados por defecto (Q131).
- El administrador puede actualizar intereses y descripción en cualquier momento.

Para volver a privado:

```json
{ "is_discoverable": false }
```

La operación desactiva la aparición en recomendaciones y búsquedas, conserva a los miembros, y rechaza automáticamente las solicitudes pendientes del grupo. Se notificará a sus solicitantes (Q137, Q143, Q175).

Respuesta `200`: detalle del grupo actualizado.
Errores: `not_found`, `forbidden`, `invalid_discovery_profile`, `validation_error`.

### 16.7 Solicitudes para unirse

#### `POST /api/discover/groups/{group_id}/join-requests`

Crea una solicitud para el grupo indicado. No requiere coincidencia de intereses; sí requiere cuenta verificada (Q141).

Respuesta `201`: `JoinRequest`.

Validaciones y reglas:

- El grupo debe existir, estar activo y ser descubrible; de lo contrario responde `404`.
- El usuario no debe ser ya integrante ni administrador del grupo.
- Solo puede existir una solicitud pendiente por usuario en toda Chatly (Q151, Q159). Si ya tiene una, responde `409 pending_join_request_exists`; puede seguir explorando, pero las demás acciones de solicitud quedan deshabilitadas.
- No puede repetir una solicitud pendiente para el mismo grupo.
- Tras un rechazo manual del mismo grupo, se aplica una espera de 7 días. El grupo sigue visible durante ese tiempo, pero no se puede volver a solicitar (Q129, Q147, Q169).
- La salida voluntaria de un grupo no genera por sí misma espera de 7 días (Q145).
- La solicitud vence a los 14 días (`expires_at = created_at + 14 days`) si no se resuelve (Q160).
- No existe endpoint de cancelación.
- La solicitud y sus cambios se conservan para auditoría, aunque no exista una pantalla de historial para el usuario.

Errores: `group_not_discoverable`, `already_member`, `pending_join_request_exists`, `join_request_cooldown`, `group_full`, `validation_error`.

#### `GET /api/me/join-request`

Devuelve únicamente la solicitud pendiente actual del actor, o `null` si no tiene ninguna. No devuelve solicitudes resueltas ni un historial (Q159, Q177).

#### `GET /api/conversations/{conversation_id}/join-requests`

Solo administrador activo. Devuelve solicitudes pendientes de su grupo ordenadas de la más antigua a la más reciente (Q161, Q170, Q171).

Devuelve `AdminJoinRequestItem[]`. Cada elemento incluye fotografía, nombre visible, alias, intereses compartidos y fecha de solicitud. No devuelve correo electrónico (Q157). Los intereses mostrados son únicamente los coincidentes con la temática del grupo y se revelan al administrador porque el usuario ha solicitado incorporarse; esto no vuelve público el perfil ni lo incorpora a recomendaciones de personas.

#### `POST /api/conversations/{conversation_id}/join-requests/{request_id}/accept`

Solo administrador activo.

- Si la solicitud sigue pendiente, el grupo es descubrible y hay una plaza, el usuario se incorpora inmediatamente y comienza un nuevo periodo de membresía (Q153).
- Si el solicitante ya había pertenecido al grupo, se aplica la regla histórica de Q162/Q158: recupera sus periodos anteriores y el nuevo, pero no los mensajes del intervalo fuera del grupo.
- Si el grupo ya tiene 10 integrantes, se impide el ingreso y la solicitud se rechaza automáticamente por `group_full`; nunca se supera el límite (Q130, Q176).
- Si la solicitud venció o dejó de estar pendiente, no se crea una membresía.

Respuesta `200`:

```json
{
  "request": { /* JoinRequest */ },
  "membership": { "user_id": "...", "joined_at": "...", "role": "member" }
}
```

`membership` es `null` si el grupo ya está completo. En ese caso la solicitud queda en `rejected` con motivo `group_full`; este endpoint no devuelve `409` en ese flujo.
Errores: `join_request_not_pending`, `not_found`, `forbidden`.

#### `POST /api/conversations/{conversation_id}/join-requests/{request_id}/reject`

Solo administrador activo. No acepta motivo ni texto adicional (Q162, Q166).

Marca la solicitud como `rejected`, registra el rechazo manual y activa la espera de siete días para ese mismo grupo (Q129, Q147, Q169).
Respuesta `200`: `JoinRequest` actualizado.
Errores: `join_request_not_pending`, `not_found`, `forbidden`.

### 16.8 Transiciones automáticas y notificaciones visuales

Las siguientes transiciones se ejecutan en la misma transacción que la operación que las provoca:

| Evento | Transición |
|---|---|
| El administrador añade al solicitante al grupo solicitado | La solicitud pasa a `accepted`; se crea una sola membresía (Q144). |
| Se añade al usuario a otro grupo | Su solicitud pendiente anterior se marca `rejected` automáticamente (Q166). |
| El grupo alcanza 10 integrantes | Las demás solicitudes pendientes del grupo se marcan `rejected` por `group_full` (Q130). |
| El administrador desactiva la descubribilidad | Las solicitudes pendientes del grupo se marcan `rejected` por `group_private` (Q137, Q143). |
| Pasan 14 días sin respuesta | La solicitud pasa a `expired` y se libera el límite global (Q160). |
| El administrador acepta/rechaza | Se registra el resultado correspondiente. |

Las notificaciones serán avisos visuales internos: el administrador recibe un aviso al llegar una solicitud y el solicitante al resolverse o expirar (Q154, Q160). No se añaden notificaciones push ni una sección «Mis solicitudes» o historial (Q177). Los cambios de estado se emitirán como eventos Realtime para que la interfaz muestre el aviso; el estado definitivo permanece en `solicitudes_union`.

**Ejecución de caducidad:** un job de `pg_cron` ejecuta `app.expire_pending_join_requests()` cada 15 minutos como `chatly_app`. La función localiza solicitudes `pending` con `vence_en <= now()`, las marca `expired`, escribe auditoría y publica `join_request.resolved` con `app.publish_social_event(...)` en la misma transacción. La operación de creación/consulta de solicitudes también comprueba y resuelve vencimientos atrasados antes de aplicar el límite de una solicitud pendiente. La entrega del aviso es best-effort, pero el estado persistido nunca depende del job.

### 16.9 Exclusiones sociales de la V1

No se crearán amistades, seguidores/seguidos, solicitudes de contacto, solicitudes de conversación, bloqueo, reportes ni moderación avanzada (Q150, Q179). La relación entre usuarios se limita a conversaciones privadas y membresías de grupos.
