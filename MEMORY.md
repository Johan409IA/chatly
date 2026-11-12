# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- **Iteración 1 (arquitectura de backend) completa y verificada** en `arquitectura-backend`.
- **Iteración 2, tareas 1–6 hechas** (Supabase Auth, JWT/JWKS, guardas Reflex). Correos reales de Brevo **pendientes**.
- **API de autenticación implementada y probada**: 8 endpoints en `backend/api/routes/auth.py`; capas `integrations/supabase/auth_client.py`, `services/auth_service.py`, `schemas/auth.py`.
- Cookies `chatly_at` y `chatly_rt`: HttpOnly, Secure solo en producción, SameSite=Lax.
- **Migraciones aplicadas**: `0002_perfiles`, `0003_conversaciones`, `0004_mensajes`, `0005_identidad_rol`, `0005a_alias_exists`, **`0005b_intereses`** (`alembic_version = 0005b_intereses`).
- **`0005b_intereses`**: `categorias_interes`, `intereses` (semilla: 5 categorías, 16 intereses), `intereses_usuario`, `perfiles.visibilidad_publica`, `app.catalogo_intereses()` `SECURITY DEFINER`, RLS y grants. Reversible con `alembic downgrade -1` (verificado).
- **Selección opcional de intereses en el registro**: `RegisterRequest.interest_ids` (0–10), `GET /api/interests` público, bloque «Intereses (opcional)» con accordion y contador `N/10` en `/register`.
- **Servidor en Windows resuelto**: `winloop` en el grupo `dev` con marker `sys_platform == 'win32'`. Granian usa `loop=auto` y elige winloop; así psycopg async funciona con `uv run reflex run` sin flags ni servidores alternativos.
- Verificado: **64 unitarias y 21 integración passed**, `ruff check` limpio, `reflex compile --dry` OK. En vivo con `uv run reflex run` (granian + winloop): `/api/health`, `/api/interests` (5 categorías, 16 intereses) y `/register` en Playwright (catálogo cargado, contador `0/10`→`10/10`, el undécimo se bloquea con aviso).

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

## Aprendizajes y errores a evitar
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

## Próximos pasos
- Probar alta con correo real (Brevo + plantilla Supabase) y Redirect URL `/auth/confirm`.
- Revisión de la migración y su RLS por dos integrantes (pendiente, regla de AGENTS.md).
- Verificado en local con Windows: `/api/health`, `/api/interests` y el bloque de intereses de `/register` responden con granian + winloop.
- Falta el envío real del formulario con correo (crea usuario en Supabase y envía email); hacerlo con una cuenta de prueba y limpiarla.
- Middleware de rate limit (§14) y endpoints sociales pendientes.
- Continuar con `0006`–`0012` y cerrar con `0013`/`0014`; revisar RLS/grants con `supabase db advisors`.
- Al desplegar: `API_PUBLIC_URL`, `CORS_ORIGINS` y variables de pool.
