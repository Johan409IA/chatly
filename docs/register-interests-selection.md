# Selección opcional de intereses en el registro

## Decisiones cerradas (confirmadas)
1. **Migración `0005b_intereses`** (`down_revision = 0005a_alias_exists`): se aplica ahora, no renumera `0006`–`0012` (que ya están reservadas en `docs/database-schema.md:849-855`). `0013_descubrimiento_social` queda solo con lo social puro.
2. **Catálogo público vía `app.catalogo_intereses()` `SECURITY DEFINER`** (mismo patrón que `app.alias_exists`, `migrations/versions/0005a_alias_exists.py:20-51`). Las políticas RLS del catálogo siguen exigiendo actor; no se rompe `docs/authorization-matrix.md:744`.
3. **`perfiles.visibilidad_publica` + recreación de `app.perfiles_publicos` van en esta migración** (tarea de iteración 2).

Fuente de verdad del DDL: `docs/database-schema.md` §17.1–17.3. Fuente del contrato: `docs/api-contracts.md` §4.1 (`interest_ids`), §16.1 (`InterestCategory`), §16.2 (`GET /api/interests`).

## 1. Migración `migrations/versions/0005b_intereses.py` (nuevo)
Estilo idempotente de `0002_perfiles.py` (`create … if not exists`, `do $$ … $$` para grants):
- Tablas de §17.2: `public.categorias_interes`, `public.intereses` con sus índices (`uq_*_nombre`, `ix_intereses_categoria_activos`).
- Tabla §17.3: `public.intereses_usuario` (`PK (usuario_id, interes_id)`, `ix_intereses_usuario_interes`).
- Semilla del catálogo (línea 974 de `database-schema.md`, `orden` 1..5): Tecnología (Programación, IA, Ciberseguridad, Desarrollo web), Negocios (Marketing, Ventas, Emprendimiento), Diseño (UI/UX, Diseño gráfico, Ilustración), Entretenimiento (Música, Cine, Videojuegos), Deportes (Fútbol, Baloncesto, Fitness). Inserción idempotente (`where not exists` por nombre).
- `alter table public.perfiles add column visibilidad_publica boolean not null default true` + índice `ix_perfiles_visibles_descubrimiento` (§17.1).
- Recrear `app.perfiles_publicos` con `visibilidad_publica` incluida (§17.1).
- `app.catalogo_intereses()`:
  ```sql
  create or replace function app.catalogo_intereses()
  returns table (categoria_id uuid, categoria text, categoria_orden int, interes_id uuid, interes text)
  language sql stable security definer set search_path = public, pg_temp
  as $$ select c.id, c.nombre, c.orden, i.id, i.nombre
        from public.categorias_interes c
        join public.intereses i on i.categoria_id = c.id
        where c.activa = true and i.activo = true
        order by c.orden, lower(c.nombre), lower(i.nombre) $$;
  ```
  `revoke all … from public` + `grant execute … to chatly_app` (guarda de rol como en `0005a`).
- RLS (enable en las 3 tablas) + políticas:
  - `categorias_interes` / `intereses`: `select to chatly_app` **con actor**, tal como `authorization-matrix.md` §6.1 (no se toca).
  - `intereses_usuario`: solo `select` propio, `insert` propio y `delete` propio (`usuario_id = (select app.current_actor_id())`). **No** se crea la política de terceros de §6.2 porque depende de `app.is_verified_actor()`, que no existe todavía (se añade en `0013`).
- Grants: `chatly_app` → `select` en `categorias_interes`/`intereses`, `select, insert, delete` en `intereses_usuario`; `revoke all` a `anon`/`authenticated`.
- `downgrade()`: dropea tablas, función, columna `visibilidad_publica` y restaura la vista anterior de `0002`.

## 2. Backend
- `Chatly/backend/schemas/interests.py` (nuevo): `InterestItemDTO(id, name)`, `InterestCategoryDTO(id, name, interests)` — nombres en inglés como el contrato (§16.1).
- `Chatly/backend/core/errors.py`: añadir `ErrorCode.INTEREST_LIMIT_EXCEEDED = "interest_limit_exceeded"` (código 422 ya definido en `api-contracts.md:64`).
- `Chatly/backend/schemas/auth.py` — `RegisterRequest`: añadir `interest_ids: list[UUID] = []`; validador: sin duplicados (`validation_error`) y máximo 10 (`interest_limit_exceeded`, 422).
- `Chatly/backend/repositories/interest_repository.py` (nuevo):
  - `list_catalog() -> list[InterestCategoryDTO]`: ejecuta `select * from app.catalogo_intereses()` con `get_app_session_factory()` (sin actor; es el mecanismo público).
  - `insert_selection(session, user_id, ids)`: `insert … select … from public.intereses i where i.id = any(:ids) and i.activo` y, si el conteo insertado ≠ `len(ids)`, lanza `ValidationError` (revierte toda la transacción). Recibe la sesión para ejecutarse dentro de la transacción del perfil.
- `Chatly/backend/repositories/profile_repository.py` — `create_profile(…, interest_ids)`: tras insertar perfil y contacto, llama a `insert_selection` en la misma `actor_transaction`. Defensa en profundidad: el filtro `activo` vive en SQL.
- `Chatly/backend/services/auth_service.py` — `register()`: antes de `sign_up`, valida que todos los IDs existan y estén activos contra `list_catalog()` (evita usuarios huérfanos en Supabase Auth si un ID es inválido); pasa `interest_ids` a `create_profile`.
- `Chatly/backend/api/routes/interests.py` (nuevo): `GET /api/interests` → `list[InterestCategoryDTO]`, `Cache-Control: public, max-age=3600` (§16.2). Registrar en `Chatly/Chatly.py` (`include_router`); CORS ya permite GET.
- `tests/unit/test_auth_api.py` (los fakes `_FakeProfileRepository` capturan `interest_ids`).

## 3. Frontend (Reflex 0.10: setters explícitos)
- `Chatly/state/auth_state.py`:
  - Campos: `interest_catalog: list[dict] = []`, `selected_interest_ids: list[str] = []`.
  - `load_interests()`: se ejecuta en `on_load` de `/register`; llama directamente al repositorio del backend (evento de servidor, sin `fetch`: el catálogo no necesita cookies; la regla de `fetch` aplica solo a operaciones que fijan sesión). Si está vacío, se carga una vez.
  - `toggle_interest(interest_id)`: añade/quita; si ya hay 10, ignora y muestra aviso («Puedes elegir hasta 10 intereses»).
  - `handle_register`: incluye `"interest_ids": self.selected_interest_ids` en el payload.
- `Chatly/pages/auth/register.py`: bloque opcional **«Intereses (opcional)»** bajo «Género», con contador `N/10`:
  - `rx.accordion` con una sección por categoría.
  - Intereses como `rx.badge` clicables (`type="button"` para no enviar el formulario; `variant="solid"` cuando está seleccionado, `outline` si no).
  - Etiqueta: «Puedes omitirlos y configurarlos después desde tu perfil».

## 4. Pruebas
- `tests/unit/test_auth_api.py`: registro con `interest_ids` los persiste; `>10` → 422 `interest_limit_exceeded`; duplicados → 422; ID desconocido/inactivo → 422.
- `tests/unit/test_interests_api.py` (nuevo): `GET /api/interests` devuelve categorías con `Cache-Control: public, max-age=3600` (repositorio falso).
- `tests/integration/test_interests_rls.py` (nuevo, estilo `test_rls_context.py`): el catálogo se lee **sin actor** vía `app.catalogo_intereses()`; `intereses_usuario`: insert propio permitido, ajeno bloqueado (RLS), select propio visible; `perfiles.visibilidad_publica` por defecto `true` y visible en `app.perfiles_publicos`.

## 5. Documentación (obligación del proyecto)
- `docs/database-schema.md`: fila nueva `0005b_intereses` en §15; `0013_descubrimiento_social` pierde «Visibilidad pública del perfil, catálogo y relaciones de intereses»; nota de §17 apunta a `0005b`.
- `docs/authorization-matrix.md`: §6.1 anota que el endpoint público usa `app.catalogo_intereses()`; §6.2 anota que la política de terceros queda en `0013` (depende de `app.is_verified_actor()`).
- `docs/roadmap.md`: línea 71 (`0005b` aplicada ahora) y marcar tareas 225–228 de la iteración 2.
- `MEMORY.md`: estado, decisiones (por qué) y errores a evitar. `docs/api-contracts.md` no cambia (el contrato ya define todo).

## Fuera de alcance
`PUT /api/me/interests` (edición desde perfil), política de terceros + `app.is_verified_actor()`, UI de `visibilidad_publica`, intereses de grupos y todo lo social de `0013`.

## Verificación
1. `uv run alembic upgrade head` (pide confirmación antes de aplicar) y comprobar `alembic downgrade -1` reversible.
2. `uv run pytest tests/unit` y `uv run ruff check .` / `uv run ruff format .` limpios.
3. `uv run reflex run` + E2E con **playwright-cli** (regla de AGENTS.md): el registro muestra el accordion, el contador `N/10` frena el undécimo interés, alta sin intereses y con intereses termina en `/verify-pending`, y las filas aparecen en `intereses_usuario` al confirmar.
4. `GET /api/health` sigue respondiendo `{"status":"ok"}`; `GET /api/interests` devuelve el catálogo sin sesión.
5. La migración y su RLS se revisan con dos integrantes (regla de AGENTS.md).
