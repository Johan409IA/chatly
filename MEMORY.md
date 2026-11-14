# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- **Desplegada en Render (2026-11-14)**: https://chatly-3lh3.onrender.com — servicio `srv-dbsdbjdg1s2s73es70cg` (Docker, plan Free, proyecto `chatly`, rama `main`, auto-deploy por commit). Verificado: `/api/health`, `/api/interests`, `/login`, `/register` y eventos por websocket (Playwright). `FRONTEND_URL`/`CORS_ORIGINS` se derivan de `RENDER_EXTERNAL_URL` (`settings.py`). **Pendiente en Supabase**: Site URL y Redirect URL `https://chatly-3lh3.onrender.com/auth/confirm`.
- **Iteración 1 (arquitectura de backend) completa y verificada** en `arquitectura-backend`.
- **Iteración 2, tareas 1–6 hechas** (Supabase Auth, JWT/JWKS, guardas Reflex). Correos reales de Brevo **pendientes**.
- **API de autenticación implementada y probada**: 8 endpoints en `backend/api/routes/auth.py`; capas `integrations/supabase/auth_client.py`, `services/auth_service.py`, `schemas/auth.py`.
- Cookies `chatly_at` y `chatly_rt`: HttpOnly, Secure solo en producción, SameSite=Lax.
- **Migraciones aplicadas**: `0002_perfiles`, `0003_conversaciones`, `0004_mensajes`, `0005_identidad_rol`, `0005a_alias_exists`, **`0005b_intereses`** (`alembic_version = 0005b_intereses`).
- **`0005b_intereses`**: `categorias_interes`, `intereses` (semilla: 5 categorías, 16 intereses), `intereses_usuario`, `perfiles.visibilidad_publica`, `app.catalogo_intereses()` `SECURITY DEFINER`, RLS y grants. Reversible con `alembic downgrade -1` (verificado).
- **Selección opcional de intereses en el registro**: `RegisterRequest.interest_ids` (0–10), `GET /api/interests` público, bloque «Intereses (opcional)» con accordion y contador `N/10` en `/register`.
- **Servidor en Windows resuelto**: `winloop` en el grupo `dev` con marker `sys_platform == 'win32'`. Granian usa `loop=auto` y elige winloop; así psycopg async funciona con `uv run reflex run` sin flags ni servidores alternativos.
- Verificado: **66 unitarias y 21 integración passed**, `ruff check` limpio, `reflex compile --dry` OK. En vivo con `uv run reflex run` (granian + winloop): `/api/health`, `/api/interests` (5 categorías, 16 intereses) y `/register` en Playwright (catálogo cargado, contador `0/10`→`10/10`, el undécimo se bloquea con aviso).
- **Recuperación de contraseña con flujo `token_hash`**: el enlace aterriza en `/reset-password?token_hash=…&type=recovery`; `POST /api/auth/reset-password` recibe `token_hash` (antes `token`), lo canjea con `verify_token_hash(type=recovery)` y cambia la contraseña con el access token (sesión de recuperación: Supabase no pide la actual). PENDIENTE configurar en el dashboard la plantilla «Reset password»: `<a href="{{ .SiteURL }}/reset-password?token_hash={{ .TokenHash }}&type=recovery">Restablecer contraseña</a>`.
- **Login y registro rediseñados** según `assets/ux-ui/`: layout de dos columnas con panel de marca (red de nodos en SVG) + panel oscuro; el registro es un **asistente de 5 pasos** (nombre → correo/alias → contraseña → fecha/género → intereses). Estilos en `assets/auth.css` (se incluye con `rx.App(stylesheets=["auth.css"])`); layout en `Chatly/components/auth_layout.py`.
- **README actualizado**: funcionalidades sociales que faltaban (intereses y sugerencias de personas, grupos descubribles y solicitudes) + configuración de arranque (tres URLs de BD, `alembic upgrade head`, SMTP y Redirect URL `/auth/confirm`, puertos 3000/8000, comandos de test y lint).

## Diseño social cerrado (docs)
- `GET /api/interests` **público** (el registro no tiene sesión); el resto de endpoints sociales exige verificado.
- El catálogo se lee **sin actor** solo con `app.catalogo_intereses()`; las políticas RLS del catálogo siguen exigiendo actor.
- `intereses_usuario`: por ahora solo selección propia; la política de terceros depende de `app.is_verified_actor()` (llega en `0013`).
- Descubrir: orden por coincidencias y empate `md5(seed || ':' || id)`; cursor firmado con `seed`, `after_count`, `after_hash`, `after_id`.
- Caducidad: **`pg_cron`** disponible (1.6.4, no instalado), job cada 15 min como `chatly_app`; `app.expire_pending_join_requests()` expira y publica `join_request.resolved`.
- Broadcast social: `app.publish_social_event(event, target_user_id, payload)` `SECURITY DEFINER`, `EXECUTE` solo `chatly_app`. `realtime.send` **no** es `SECURITY DEFINER`.
- Límites: Descubrir 30/min, crear solicitud 10/min, consultar la propia 60/min.
- `solicitudes_union` solo grupos: columna `tipo='group'` + FK compuesta `(conversacion_id, tipo)` con `uq_conversaciones_id_tipo`.
- Cadena de migraciones: `0006`–`0012` base y `0013`/`0014` social pendientes.

## Decisiones (y por qué)
- Tres conexiones: `DATABASE_URL` (DDL), `APP_DATABASE_URL` (runtime, `chatly_app`) y `TEST_DATABASE_URL` (pruebas, `chatly_app`).
- **`chatly_app` NO hereda `authenticated`**: `app.current_actor_id()` es `SECURITY DEFINER`.
- Nombres en español para tablas/columnas; inglés para clases/funciones/variables.
- El registro valida los `interest_ids` **antes** de `sign_up` (contra el catálogo activo) para no dejar usuarios huérfanos en Supabase Auth; la inserción va en la misma `actor_transaction` del perfil y el filtro `activo` vive en el SQL.
- Límite de 10 validado en el esquema (`422 interest_limit_exceeded`), duplicados (`422 validation_error`).
- `load_interests()` es un evento de servidor que llama al repositorio: el catálogo no necesita cookies (la regla de `fetch` aplica a lo que fija sesión).
- Estado de la UI con dataclasses (`InterestCategory`/`InterestItem`): `rx.foreach` anidado exige tipos declarados.
- Login/logout/refresh vía fetch HTTP (cookies HttpOnly); login recarga completa.
- **Asistente de registro**: `AuthState.register_step` (1..5) + `next_step`/`prev_step`/`reset_register`; la validación por paso reutiliza los validadores existentes (`validate_register`, `password_is_strong`, regex de alias/correo, edad 18–120). Si el backend rechaza un campo, se vuelve al paso que lo contiene (`_ERROR_STEP`).
- **Los errores por campo son vars sueltas** (`error_email`, `error_alias`, …), no un dict: leer `state.dict["clave"]` en el cliente devuelve `undefined` si la clave no existe y el mensaje no se pinta.

## Aprendizajes y errores a evitar
- **`reflex db migrate` sale con código 1** si `rxconfig.py` no define `db_url`, y en el contenedor eso aborta el arranque antes de Caddy. La app usa Alembic: `CMD ... alembic upgrade head` (condicionado a `-f alembic.ini`).
- **El dominio de Render no se conoce al crear el servicio** (añade sufijo: `chatly-3lh3`) y la CLI no permite editar env vars después; por eso la URL pública se deriva de `RENDER_EXTERNAL_URL`.
- **El build de Docker necesita la configuración válida**: `reflex export` importa la app, así que el `RUN` del export pasa marcadores ficticios (`.env` está en `.dockerignore`).
- **I/O síncrono bloquea el event loop (granian avisa con >200 ms)**: la descarga del JWKS (`PyJWKClient` usa `urllib`) y `create_async_engine` (importa el dialecto de PostgreSQL) son síncronas. Solución: warm-up `_warm_up` en el lifespan del API de `Chatly.py` (Reflex SÍ ejecuta el lifespan del `api_transformer`; log "Warm-up completado" lo confirma) y verificación JWT con `asyncio.to_thread` en `auth_service`, `deps.require_actor` y las guardas de `SessionState` (ahora `async def`).
- **`rx.call_script` evalúa el código con `eval`**: debe ser una EXPRESIÓN (`(async () => {...})()`). Si es solo la función, el callback recibe un valor no serializable y el servidor recibe el payload vacío (`TypeError: ... missing 1 required positional argument`).
- **En Windows granian fuerza `ProactorEventLoop`** (`granian/_loops.py`), que psycopg async no admite: toda consulta a la BD falla con `InterfaceError`. Se resuelve con `winloop` en el grupo `dev` (marker win32): granian lo registra y `loop=auto` lo prefiere. **No usar uvicorn**: Reflex llama a `uvicorn.run(reload=True)` sin guarda `__main__`, y en Windows el spawn re-ejecuta el CLI y el arranque se cuelga; además el CLI no lee `.env` para `REFLEX_USE_GRANIAN`.
- **`NODE_ENV=production` heredado del proceso padre rompe el frontend en dev**: Vite/React resuelven el runtime de producción y el SSR falla con `jsxDEV is not a function`. No está definido en el usuario ni en la máquina; en una terminal limpia no existe. Para pruebas automatizadas, lanzar con `NODE_ENV=development`.
- `RequestValidationError` se importa de `fastapi.exceptions`.
- Reflex: cookies solo server-side; `@rx.page` + `add_page` duplica rutas; guardas devuelven `rx.redirect` o `[]`.
- Ruff B008: usar `Annotated[T, Depends…]`. `pytest tests/unit`; integración se cuelga sin red.
- Violación de RLS → `ProgrammingError` 42501. No editar el bloque `reflex managed` de AGENTS.md.
- En Windows, `alembic upgrade --sql` con emojis falla con `UnicodeEncodeError` cp1252; usar `PYTHONIOENCODING=utf-8`.
- `create or replace view` no puede quitar columnas: en el `downgrade` hay que `drop view` y recrearla.
- `insert … select` con lista de UUID: pasar `cast(:ids as uuid[])` y `returning` para contar lo insertado.
- **El navegador bloquea el `submit` del formulario**: un `input type="email"` con valor inválido impide el envío (validación HTML5) y, con el botón de envío deshabilitado, la tecla Enter tampoco dispara el evento. Por eso los formularios de auth van con `no_validate=True` y el botón «Siguiente» nunca se deshabilita: valida al pulsar y muestra el error bajo el campo.
- **En Windows, el worker de granian muere al recargar** (`ModuleNotFoundError: No module named 'fastapi'`): el backend queda caído y los eventos por WebSocket dejan de llegar (parece un bug de estado). Reiniciar `uv run reflex run` y recargar la página.

## Próximos pasos
- Configurar la plantilla «Reset password» de Supabase (flujo `token_hash`, ver arriba) y probar el ciclo completo de recuperación con la cuenta de prueba.
- Probar alta con correo real (Brevo + plantilla Supabase) y Redirect URL `/auth/confirm`; usar una cuenta de prueba y limpiarla.
- Revisión de la migración y su RLS por dos integrantes (pendiente, regla de AGENTS.md).
- Middleware de rate limit (§14) y endpoints sociales pendientes.
- Continuar con `0006`–`0012` y cerrar con `0013`/`0014`; revisar RLS/grants con `supabase db advisors`.
- Configurar Site URL y Redirect URL de producción en Supabase y probar registro/recuperación reales. Opcional: activar «After CI Checks Pass» en Render (Dashboard → Settings) para que el deploy espere al workflow `CI`.
- Plan Free: el servicio se duerme a los 15 min sin tráfico (cold start ~1 min); con tráfico real conviene subir a `0.5c-512mb`.
- Las referencias de diseño están en **`docs/ux-ui/`** (fuera de `assets/`, para que no se copien al build); `assets/` solo lleva lo que la app sirve (`auth.css`, `favicon.ico`, `icons/`, `js/`).
