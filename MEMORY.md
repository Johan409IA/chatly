# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- **Iteración 1 (arquitectura de backend) completa y verificada** en `arquitectura-backend` (sin commits).
- T1–T8 listos: Settings, Base/mixins, engine/sesiones con contexto RLS, Alembic `0001_infra` (schema `app` + `app.current_actor_id()`), errores tipados con envelope, logging JSON con redacción.
- `ruff check/format`, `pytest` (31 passed, 0 skipped), `alembic upgrade/downgrade/upgrade` y `/api/health` (`{"status":"ok"}`) verificados.
- Pruebas RLS corren como `chatly_app` vía `TEST_DATABASE_URL` (Session Pooler, usuario `chatly_app.<project_ref>`); sin conexión se saltan con mensaje claro.

## Decisiones (y por qué)
- **Pruebas contra Supabase nube**, no Postgres local: sin Docker; desvío documentado en `architecture.md` §11.
- **Dos conexiones de prueba**: admin (`DATABASE_URL`/`postgres`, solo DDL) y app (`TEST_DATABASE_URL`/`chatly_app`, aserciones RLS). `require_app_role()` falla si la conexión no es `chatly_app` o tiene BYPASSRLS.
- **`chatly_app` hereda de `authenticated`** (`alter role chatly_app inherit;` + `grant authenticated to chatly_app;`): resuelve `auth.uid()` sin helpers `SECURITY DEFINER` ni roles temporales; las políticas llaman a `app.current_actor_id()` directo.
- **Nombres en español** para tablas/columnas (`creado_en`, `propietario_id`) y en inglés para clases/funciones.
- **SelectorEventLoop en Windows**: Psycopg 3 async no funciona con ProactorEventLoop; fijado en `migrations/env.py` y `tests/conftest.py`.
- Pool y logging configurables: `DB_POOL_SIZE/DB_MAX_OVERFLOW/DB_POOL_TIMEOUT/DB_POOL_RECYCLE/LOG_LEVEL` en `.env.example`.

## Aprendizajes y errores a evitar
- El bloque `reflex managed` de `AGENTS.md` no se edita; el contenido propio va después de los marcadores.
- `uv run reflex run` regenera `.web`; conservar `bunfig.toml`.
- `set_config(..., true)` es **local a la transacción**: imprescindible para el pool; validado con tests.
- `postgres` no puede otorgar `usage` del schema `auth` (dueño: `supabase_admin`); la vía es la membresía en `authenticated`.
- Un rol creado con NOINHERIT no hereda privilegios de sus grupos: se necesita `alter role ... inherit`.
- Una violación de RLS (`with check`) llega como `ProgrammingError` (SQLSTATE 42501), no como `IntegrityError`.
- `DROP ROLE` falla si el rol conserva grants: revocar antes de soltar.

## Próximos pasos
- Iteración 2: JWT/JWKS, tablas de negocio (`profiles`, conversaciones, mensajes, encuestas) con políticas RLS y endpoints.
- Cuando la app corra sin DDL, mover `DATABASE_URL` a `chatly_app` y dejar una URL separada solo para migraciones.
