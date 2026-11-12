# Plan — Iteración 1: Arquitectura y cimientos de backend

**Proyecto:** Chatly · **Rama de trabajo:** `arquitectura-backend` (PR hacia `develop`; sin commits/push automáticos)
**Referencia:** `docs/roadmap.md` §Iteración 1, `docs/architecture.md`, `docs/api-contracts.md`

## 1. Objetivo

Dejar la base técnica lista antes de cualquier funcionalidad visible: configuración central, engine async con pool, Alembic con `target_metadata`, mixins base (UUID/timestamps/soft delete/auditoría), mecanismo RLS de identidad por transacción probado contra Supabase, manejo uniforme de errores y logs seguros.

## 2. Decisiones confirmadas


| Tema                   | Decisión                                                                                                                                                                                |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BD de pruebas          | **Supabase nube directo** (Session Pooler, `DATABASE_URL` del `.env`). Sin Docker. Se asume el desvío respecto a `architecture.md` §12.1 (pruebas contra Supabase sin PostgreSQL local) y se documenta. |
| Nombres de campos base | Español: `id` (uuid), `creado_en`, `actualizado_en`, `eliminado_en`, `creado_por`, `actualizado_por`. Tablas y columnas en español; clases/funciones/variables en inglés.               |
| Migración `0001_infra` | Crea schema `app` + función `app.current_actor_id()` + grants. El rol `chatly_app` (sin `BYPASSRLS`) se crea **manualmente** desde el SQL editor de Supabase.                           |
| Dependencias           | **Ninguna nueva**: todo con stdlib + dependencias ya presentes en `pyproject.toml`.                                                                                                     |


## 3. Prerrequisitos manuales en Supabase (una sola vez)

1. Crear el rol de aplicación desde el SQL editor (rol propietario: el de migraciones; `chatly_app` sin `BYPASSRLS`):
   ```sql
    create role chatly_app login password '<secreto>';
    alter role chatly_app noinherit;
   ```
2. `DATABASE_URL` (rol `postgres`) para migraciones/DDL y `APP_DATABASE_URL`/`TEST_DATABASE_URL` (rol `chatly_app`) para runtime y pruebas, con el **Session Pooler** de Supabase (`...pooler.supabase.com:5432`, `?sslmode=require`).
3. Verificar atributos del rol de conexión: `select rolname, rolsuper, rolbypassrls from pg_roles where rolname in ('chatly_app','postgres');`. Ningún rol de aplicación debe tener `rolbypassrls = true`.
4. Si al final se opta por usar el rol `postgres` para las pruebas, las tablas de prueba **deben** crearse con `FORCE ROW LEVEL SECURITY` (el propietario salta RLS si no se fuerza).

## 4. Estructura de archivos

### Nuevos


| Archivo                                  | Responsabilidad                                                                   |
| ---------------------------------------- | --------------------------------------------------------------------------------- |
| `Chatly/backend/core/settings.py`        | `Settings` (Pydantic Settings) + `get_settings()` cacheado                        |
| `Chatly/backend/core/errors.py`          | `ErrorCode`, `DomainError` y subclases + handlers FastAPI                         |
| `Chatly/backend/core/logging.py`         | Logging JSON estructurado + filtro de redacción                                   |
| `Chatly/backend/database/base.py`        | `Base`, `NAMING_CONVENTION` y mixins (UUID, timestamps, soft delete, auditoría)   |
| `Chatly/backend/database/session.py`     | Engine async, `async_sessionmaker`, helper de contexto RLS, dependencia de sesión |
| `migrations/versions/0001_infra.py`      | Schema `app`, función `app.current_actor_id()`, grants condicionales              |
| `tests/conftest.py`                      | Fixtures de settings/engine/sesión y utilidades de contexto de actor              |
| `tests/unit/test_settings.py`            | Validación de configuración                                                       |
| `tests/unit/test_errors.py`              | Formato de error y códigos HTTP                                                   |
| `tests/unit/test_logging.py`             | Redacción de datos sensibles                                                      |
| `tests/integration/test_connection.py`   | Conexión, `select 1`, liberación de pool                                          |
| `tests/integration/test_transactions.py` | Commit, rollback y liberación de conexiones                                       |
| `tests/integration/test_rls_context.py`  | Aislamiento RLS y no fuga de contexto entre transacciones                         |


### Modificados


| Archivo                | Cambio                                                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `migrations/env.py`    | `target_metadata = Base.metadata`; URL desde `get_settings()`                                                      |
| `Chatly/Chatly.py`     | `FastAPI(... docs_url=None, redoc_url=None, openapi_url=None)`; registrar handlers de error; `configure_logging()` |
| `pyproject.toml`       | Registrar marker `db` (pruebas que requieren Supabase)                                                             |
| `.env.example`         | Añadir `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`, `LOG_LEVEL`                        |
| `docs/architecture.md` | Documentar desvío de pruebas contra Supabase y variables nuevas                                                    |
| `MEMORY.md`            | Estado al cierre de la iteración                                                                                   |


## 5. Tareas detalladas

### T1 — Configuración central (`backend/core/settings.py`)

- `Settings(BaseSettings)` con `SettingsConfigDict(env_file=".env", extra="ignore")`.
- Campos: `app_env: Literal["development","test","production"] = "development"`, `database_url: str`, `supabase_url: str`, `supabase_publishable_key: str`, `supabase_jwks_url: str`, `supabase_avatars_bucket: str = "avatars"`, `db_pool_size: int = 5`, `db_max_overflow: int = 10`, `db_pool_timeout: float = 30`, `db_pool_recycle: int = 1800`, `log_level: str = "INFO"`.
- `@lru_cache` en `get_settings()` para instancia única.
- Validar que `database_url` use el driver `postgresql+psycopg`.

### T2 — Base, naming convention y mixins (`backend/database/base.py`)

- `NAMING_CONVENTION = {"pk": "pk_%(table_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "ix": "ix_%(table_name)s_%(column_0_name)s"}`.
- `class Base(DeclarativeBase)` con `metadata = MetaData(naming_convention=NAMING_CONVENTION)` y `type_annotation_map` si hace falta (`datetime` → `DateTime(timezone=True)`).
- Mixins:
  - `UuidPkMixin`: `id: Mapped[uuid.UUID]`, `primary_key=True`, `server_default=text("gen_random_uuid()")`.
  - `TimestampsMixin`: `creado_en`/`actualizado_en` `timestamptz`, `server_default=func.now()` y `onupdate=func.now()`.
  - `SoftDeleteMixin`: `eliminado_en` `timestamptz | None`.
  - `AuditMixin`: `creado_por`/`actualizado_por` `uuid | None`.
- `backend/database/models/__init__.py`: re-exportar `Base` y dejar el paquete listo para los modelos de negocio (Iteración 2).

### T3 — Engine, sesiones y contexto RLS (`backend/database/session.py`)

- `create_async_engine(settings.database_url, pool_size=..., max_overflow=..., pool_timeout=..., pool_recycle=..., pool_pre_ping=True)` (driver Psycopg 3 vía URL, sin cambio de dependencias).
- `async_session_factory = async_sessionmaker(engine, expire_on_commit=False)`.
- `async def set_actor_context(session, actor_id: uuid.UUID) -> None`: ejecuta `select set_config('app.current_user_id', :uid, true)` dentro de la transacción activa.
- `@asynccontextmanager async def actor_transaction(actor_id)`: abre sesión → `async with session.begin()` → fija contexto → `yield session`; commit en éxito, rollback en excepción; `finally: await session.close()` (devuelve la conexión al pool).
- Dependencia `get_session()` para FastAPI: `async with async_session_factory() as session: yield session`.
- `async def dispose_engine()` para el cierre ordenado.

### T4 — Alembic (`migrations/env.py` + `0001_infra`)

- `env.py`: `from Chatly.backend.database.base import Base`; `target_metadata = Base.metadata`; URL desde `get_settings().database_url` (con fallback al `.ini` en modo offline); `compare_type=True`.
- `migrations/versions/0001_infra.py`:
  - **upgrade:** `create schema if not exists app`; `create or replace function app.current_actor_id() returns uuid language sql stable as $$ select coalesce(auth.uid(), nullif(current_setting('app.current_user_id', true), '')::uuid) $$;`; grants con bloque `DO` condicionado a que exista el rol (`pg_roles`): `usage` sobre `app`, `execute` sobre la función.
  - **downgrade:** eliminar función y schema `app` (solo objetos de infraestructura).
  - No crear el rol desde la migración (requiere privilegios elevados).

### T5 — Errores centralizados (`backend/core/errors.py`)

- `ErrorCode` con los códigos de `api-contracts.md` §2 (`validation_error`, `unauthorized`, `forbidden`, `not_found`, `internal_error`, etc.).
- `DomainError(Exception)` con `code`, `message` (español, segunda persona), `status_code`, `details`.
- Subclases: `ValidationError` (422), `UnauthorizedError` (401), `ForbiddenError` (403), `NotFoundError` (404), `ConflictError` (409), `RateLimitedError` (429).
- Handlers: `domain_error_handler`, `validation_exception_handler` (Pydantic → envelope) y `unhandled_exception_handler` (500 sin trazas), todos devolviendo `{"error": {"code", "message", "details"?}}`.
- Registrar en `Chatly.py`; deshabilitar OpenAPI (`docs_url=None`, `redoc_url=None`, `openapi_url=None`).

### T6 — Logging seguro (`backend/core/logging.py`)

- `configure_logging(level)` con `logging.config` y `JsonFormatter` propio: `timestamp`, `level`, `logger`, `message`, `request_id`, `actor_id`, `action`, `entity`, `duration_ms`.
- `RedactionFilter`: oculta `authorization`, `token`, `access_token`, `refresh_token`, `apikey`, `cookie`, `set-cookie`, `password`, `service_role`; enmascara correos (`j***@dominio`).
- Forzar `sqlalchemy.engine` a `WARNING` para no registrar parámetros de consulta.
- Sin dependencias nuevas.

### T7 — Pruebas

- `tests/conftest.py`: engine de sesión con la URL real; fixture `db_available` que hace `select 1` y marca `skip` con mensaje claro si no hay red/credenciales; factoría `actor_session(actor_id)`; limpieza de objetos de prueba.
- `tests/unit/test_settings.py`: defaults, lectura de `.env`, validación del driver.
- `tests/unit/test_errors.py`: envelope y códigos HTTP; Pydantic inválido → 422; excepción no controlada → 500 sin trazas.
- `tests/unit/test_logging.py`: el filtro no deja pasar secretos ni correos completos.
- `tests/integration/test_connection.py`: `select 1`; tras cerrar la sesión `engine.pool.checkedout() == 0`.
- `tests/integration/test_transactions.py`: commit persiste; rollback descarta; la conexión vuelve al pool en ambos casos.
- `tests/integration/test_rls_context.py` (marcado `db`):
  1. Fixture crea un schema/tabla de prueba (`prueba_alcance_rls`) con `ENABLE` + `FORCE ROW LEVEL SECURITY` y política `using (app.current_actor_id() = propietario_id)`, con `create table ... as`/DDL limpio y teardown `drop`.
  2. Inserta filas para los actores A y B y comprueba que cada transacción solo ve las suyas (caso de salida: petición autenticada simulada solo consulta filas permitidas).
  3. Dos transacciones **consecutivas** con actores distintos sobre la misma conexión del pool no comparten contexto.
  4. `current_setting('app.current_user_id', true)` vuelve vacío tras commit/rollback.
  5. Verifica que el rol de conexión no tenga `BYPASSRLS` (si aplica el rol de la app).

### T8 — Documentación

- `docs/architecture.md`: ajustar §12.1 (pruebas contra Supabase nube, con la justificación y el `skip` cuando no hay red) y §10 (variables de pool/log); confirmar que el diagrama de flujo §4.2 refleja el código implementado.
- `.env.example`: añadir las variables nuevas con valores por defecto.
- `MEMORY.md` al cierre: estado, decisiones (pruebas contra nube, nombres en español) y errores a evitar.
- `roadmap.md`: Al terminar todas las tareas marcar como completado las actividades del roadmap para asegurarse de cerrarlo.

## 6. Orden de implementación

1. `settings.py` → 2. `base.py` → 3. `session.py` → 4. `0001_infra` + `env.py` → 5. `errors.py` + logging → 6. pruebas → 7. documentación → 8. verificación.

## 7. Verificación (criterios de salida)


| Criterio del roadmap                                                        | Cómo se verifica                                                                |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Petición autenticada simulada solo consulta filas permitidas                | `test_rls_context.py` (caso 2)                                                  |
| Dos peticiones consecutivas con usuarios distintos no comparten contexto    | `test_rls_context.py` (caso 3)                                                  |
| Las transacciones liberan conexiones del pool                               | `test_connection.py` y `test_transactions.py` (`checkedout() == 0`)             |
| El backend consulta Supabase sin credenciales privilegiadas en el navegador | Prerrequisito del rol `chatly_app` + `DATABASE_URL` solo en `.env` del servidor |


Comandos:

```bash
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run reflex run   # /api/health → {"status":"ok"}
```

## 8. Riesgos y mitigaciones

- **Rol propietario/superusuario salta RLS** → tablas de prueba con `FORCE ROW LEVEL SECURITY`; verificar `pg_roles`.
- **Fuga de contexto entre reutilizaciones del pool** → `set_config(..., true)` + prueba de transacciones consecutivas.
- **`set_config` persistente tras rollback** → el ajuste es local a la transacción; se prueba explícitamente.
- **La migración no puede crear roles** → prerequisito manual documentado + grants condicionales con `DO`.
- **Pruebas dependen de red/Supabase** → marker `db` y `skip` explicativo; el resto de la suite sigue verde sin `.env`.
- **Alembic intenta gestionar objetos del schema `app`** → sin modelos mapeados a `app`, el autogenerate por defecto (solo schema `public`) no los toca.

## 9. Fuera de alcance (iteraciones siguientes)

- Verificación real de JWT/JWKS y guardas de rutas (Iteración 2).
- Tablas y políticas RLS de negocio (`profiles`, `conversations`, `messages`, etc.).
- Endpoints de negocio, Realtime, Storage, seed demo y CI/CD.