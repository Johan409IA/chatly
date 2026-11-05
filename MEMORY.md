# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- **Iteración 1 (arquitectura de backend) completa y verificada** en `arquitectura-backend`.
- **Iteración 2, tareas 1–6 hechas** (Supabase Auth config, JWT/JWKS, guardas Reflex). Correos reales de Brevo **pendientes de probar** (tarea 3).
- **API de autenticación implementada y probada**: `backend/api/routes/auth.py` con 8 endpoints (register, login, refresh, logout, resend-verification, forgot-password, reset-password, **confirm** §4.8 nueva). Capas: `integrations/supabase/auth_client.py` (REST, httpx), `services/auth_service.py`, `schemas/auth.py`.
- Cookies: `chatly_at` (max_age=expires_in) y `chatly_rt` (30 días decisión local), HttpOnly + Secure solo en producción + SameSite=Lax.
- **Migración `0002_perfiles` aplicada** (`alembic_version`): `perfiles` + `contactos_usuario`, vista `app.perfiles_publicos`, `app.buscar_usuario_por_correo`, triggers y RLS. Es idempotente sobre las tablas creadas antes con SQL manual. `docs/database-schema.md` reescrito con nombres en español.
- UI de auth: pantallas reales en `pages/auth/*` con `fetch` del navegador vía `rx.call_script`; ruta de confirmación `/auth/confirm` (contrato). Índice `/` «Bienvenido a Chatly».
- **Flujo probado de punta a punta en API**: CORS con credenciales verificado (preflight y 422/401 con `Origin: localhost:3000`); login contra Supabase responde `invalid_credentials` en español. Falta la prueba con correo real.
- Verificado: 53 unitarias passed, `ruff check` limpio, `reflex compile --dry` OK.

## Decisiones (y por qué)
- **dos conexiones de prueba** admin (`DATABASE_URL`/DDL) y app (`TEST_DATABASE_URL`/`chatly_app`), sin BYPASSRLS; `chatly_app` hereda de `authenticated`.
- **Nombres en español** para tablas/columnas e inglés para clases/funciones/variables.
- **Login/logout/refresh SIEMPRE vía fetch HTTP del navegador** (no eventos Reflex): las cookies HttpOnly solo se fijan en una respuesta HTTP real. `auth_state` ya usa `rx.call_script` contra los endpoints reales (sin mock).
- `register` **persiste `perfiles` + `contactos_usuario`** tras el signup con `actor_transaction` (`set_config`); pre-valida alias (`alias_taken`) y `sign_up` envía `redirect_to=/auth/confirm`. `login` devuelve `alias`/`display_name` del perfil.
- Reenvío/recuperación responden **202 siempre** (no revelan cuentas); rate limit §14 (3/15 min) pendiente con middleware.
- `/auth/confirm` acepta `token_hash` (verify), `code` PKCE (token exchange) o tokens en el fragmento (implícito ya confirmado). Probar con correo real.
- **CORS** (`allow_credentials=True`, orígenes de `CORS_ORIGINS`) y `fetch` absoluto con `credentials: include`. `API_PUBLIC_URL` apunta al API; el host se toma de `window.location` para que 127.0.0.1 comparta cookie.
- Login hace **recarga completa** (`window.location.assign('/')`): la guarda solo ve la cookie en una petición HTTP nueva.
- Reflex 0.10: `state_auto_setters=False`; los inputs usan setters explícitos (`set_email`, etc.).
- JWT: caché por digest del token; audience `authenticated` + project_ref; leeway 30 s.
- Brevo Free: 300 correos/día; registrado en `architecture.md` §5.5.
- SelectorEventLoop en Windows (Psycopg 3 async); `set_config(..., true)` local a la transacción.
- Pruebas API: patrón de `test_deps.py` — TestClient + `dependency_overrides` + `get_jwt_verifier` monkeyparcheado; sin red.

## Aprendizajes y errores a evitar
- `RequestValidationError` se importa de `fastapi.exceptions`, no de `fastapi`.
- No confiar en la primera escritura de texto: leer el archivo editado cercano al cambio (una edición anterior rompió un bloque).
- Reflex: cookies solo server-side (`self.router.headers.cookie`); `@rx.page` + `add_page` del mismo componente duplica rutas (RouteValueError); guardas devuelven `rx.redirect` o `[]` desde `on_load`.
- Ruff B008: `Annotated[T, Depends…]`, no default. `pytest -q` completo se cuelga en integración sin red; usar `pytest tests/unit`.
- Violación de RLS → `ProgrammingError` 42501. `uv run reflex run` regenera `.web`; conservar `bunfig.toml`; no editar bloque `reflex managed` de AGENTS.md.

## Próximos pasos
- Probar el alta con un correo real (SMTP Brevo) y la plantilla de confirmación de Supabase; revisar la Redirect URL `/auth/confirm`.
- Middleware de rate limit (§14: reenvío 3/15 min por IP+correo).
- Alinear `authorization-matrix.md`, `architecture.md` y `realtime-events.md` con los nombres en español (los JSON de `api-contracts.md` no se tocan).
- Al desplegar: `API_PUBLIC_URL` (vacío si mismo origen) y `CORS_ORIGINS` del dominio real.
