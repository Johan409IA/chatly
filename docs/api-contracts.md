# Chatly — Contratos de API

> **Estado:** propuesta para revisión del equipo.
> **Implementación:** FastAPI integrado en Reflex mediante `api_transformer`. Un solo servidor.
> **Base:** Q1–Q112, `docs/database-schema.md`, `docs/authorization-matrix.md` y `docs/realtime-events.md`.
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
| `duplicate_request` | 200 | Reintento idempotente; se devuelve el recurso existente |
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
  "gender": "masculino"
}
```

Reglas: `age` derivada de `birth_date`; `birth_date` **no** aparece aquí. Visible para usuarios autenticados y verificados (Q109, Q110).

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
  "members_count": 5
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
  "gender": "masculino"
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

> El registro no inicia sesión de chat: el correo debe confirmarse primero (Q15).

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
  "gender": "masculino"
}
```

| Campo | Regla |
|---|---|
| `display_name` | 2–60 (Q111) |
| `alias` | 3–20, formato de Q57, único, 1 cambio/30 días (Q107) |
| `birth_date` | Edad 18–120 (Q109) |
| `gender` | `femenino` o `masculino` (Q110) |

- Cada cambio se audita (Q43).
- Respuesta `200` con `ProfileMe`.
- Errores: `alias_taken`, `alias_change_too_soon`, `validation_error`.

### 5.3 `POST /api/me/avatar`

Finaliza una subida directa a Storage.

```json
{ "object_path": "0f8c2a4e-.../1b2c3d4e-....webp" }
```

Flujo:

1. El navegador sube el archivo a `avatars/{user_id}/{uuid}.{ext}` con `supabase-js` y el JWT del usuario.
2. El bucket aplica límite de 2 MB y tipos JPEG/PNG/WebP (Q18).
3. El backend hace `HEAD` del objeto, verifica tipo y tamaño, y actualiza `profiles.avatar_path`.
4. El archivo anterior se conserva en Storage; solo cambia la referencia vigente (Q80).
5. Respuesta `200` con `{ "avatar_url": "..." }` (URL firmada con **10 minutos** de vigencia).

Errores: `invalid_avatar`, `not_found`.

### 5.4 `DELETE /api/me/avatar`

Elimina la referencia vigente y vuelve al avatar predeterminado. El archivo se conserva (Q80, Q18). Respuesta `204`.

### 5.5 `GET /api/profiles/{user_id}`

Devuelve `ProfilePublic`. No incluye correo ni fecha de nacimiento. `404` si no existe o está borrado.

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

```json
{ "user_id": "0f8c2a4e-..." }
```

- Si ya existe la conversación privada de la pareja, devuelve `200` con la existente (Q20).
- Si no, `201`.
- Errores: `not_found`, `forbidden` (usuario no verificado).

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

Solo administrador activo (Q81). Respuesta `201` con la membresía creada. Errores: `already_member` (Q86), `conversation_full` (Q8), `not_found`.

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
| Paginación | 50 inicial, 30 anteriores | Q94 |

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
| Crear directa | 200/201 | 401, 403, 404 |
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

---

## 14. Límites de frecuencia

Se aplican en la capa HTTP (FastAPI) y en memoria del proceso. Al ser una sola instancia y sin Redis, los contadores se reinician al reiniciar el servicio; es aceptable para la demostración y se documenta como limitación.

| Operación | Límite | Clave |
|---|---|---|
| Login | 10 intentos / 15 min | IP + correo normalizado |
| Reenvío de verificación | 3 / 15 min | IP + correo |
| Recuperación de contraseña | 3 / 15 min | IP + correo |
| Búsqueda de usuarios | 30 / min | usuario autenticado |
| Envío de mensajes | 30 / min | usuario autenticado |
| Reacciones | 60 / min | usuario autenticado |

- Al exceder: `429 rate_limited` con cabecera `Retry-After` en segundos.
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
