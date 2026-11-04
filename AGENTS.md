<!-- reflex managed begin (do not edit inside this block; add custom content outside the markers) -->
# Agents

This project uses the **Reflex agent skills** � up-to-date knowledge for building full-stack Python web apps with [Reflex](https://reflex.dev). Install them first, then use them as described below.

## Installing the Skills

Before working on this project, make sure the Reflex skills are available to you.

### Claude Code

If the skills are not already available, install them yourself by running these shell commands:

```bash
claude plugin marketplace add reflex-dev/agent-skills
claude plugin install reflex@reflex-agent-skills
```

Newly installed plugins load on the next session. After installing, tell the user to restart the session so the skills auto-load; until then, read the skill files directly from `~/.claude/plugins/` when you need them.

### Other agents (Cursor, OpenCode, Codex, Pi)

```
npx skills add reflex-dev/agent-skills
```

Or clone https://github.com/reflex-dev/agent-skills and copy the `skills/` folders into your agent's skill directory (see the repo README for paths).

### Verifying

Before writing or editing any Reflex code, confirm these three skills are available: `reflex-docs`, `setup-python-env`, and `reflex-process-management`. If they are not, STOP and run the install step above � do not proceed without them.

## Using the Skills

### Reflex documentation

For anything about Reflex APIs � components, state management, events, styling, database, routing, authentication � use the **reflex-docs** skill rather than relying on memory. It carries current, version-accurate docs.

### Initializing a new Reflex project

When starting a new Reflex project or setting up a development environment, you **must** follow the **setup-python-env** skill before doing anything else.

Do not skip any steps. Do not assume a virtual environment or Reflex is already available � always verify first by following the skill's instructions in order.

After the environment is ready and Reflex is installed, run:

```bash
reflex init
```

Then proceed with the user's request.

### Managing a Reflex process

When you need to compile, run, reload, or debug a Reflex application, follow the **reflex-process-management** skill for the correct sequence and error investigation steps.
<!-- reflex managed end -->

# AGENTS.md — Chatly

Chatly: app web responsive de mensajería (español) con chats privados/grupales y encuestas, instalable como PWA. V1 sin CI/CD ni protección de rama.

## Stack y estructura
- Python 3.13.7 + uv; Reflex (full-stack) + FastAPI integrado; SQLAlchemy 2 async, Psycopg 3, Alembic, Pydantic 2, Pydantic Settings, PyJWT; Supabase (Auth/PostgreSQL/Realtime/Storage).
- App Reflex en `Chatly/` (`pages`, `components`, `state`, `backend/{api,services,repositories,database,core,integrations}`); tests en `tests/unit`; docs en `docs/`; migraciones en `migrations/`.

## Comandos
- `uv sync` · `uv run reflex run` (UI :3000, API :8000) · `uv run pytest` · `uv run ruff check .` · `uv run ruff format .` · `uv run alembic upgrade head`

## Convenciones
- UI y mensajes en español. Conventional Commits. Ruff: line-length 100, target py312. Identidad del usuario se deriva siempre del JWT, nunca de un `user_id` del cliente. RLS por transacción (rol sin BYPASSRLS).

## Reglas de dominio / trampas
- Un solo backend Reflex (no segundo FastAPI). Sin Redis (una instancia). Sin CI/CD en GitHub. `bunfig.toml` usa espejo npmmirror por bloqueo de red a npmjs.org. No editar el bloque "reflex managed" de este archivo.

## Forma de trabajar
- Planificar antes de cambios grandes; ramas `feature/*` → `develop` → `main`; migraciones y RLS revisadas por dos integrantes.
- Al terminar cada tarea, actualizar `MEMORY.md` con estado, decisiones y errores a evitar. Mantenerlo breve (~50 líneas). Proponer mover reglas permanentes a este archivo.
- Usar nombres en español para las tablas y campos de la base de datos, y para los modelos Pydantic y SQLAlchemy. Usar nombres en inglés para las clases de Python, funciones, variables y métodos.
- Usar playwright cli para pruebas end-to-end (E2E) de la UI. No usar Selenium ni Cypress, cuando sea necesario.

## Memoria
- Al empezar, lee `MEMORY.md` para conocer el estado del proyecto y las decisiones tomadas.
- Al terminar una tarea, actualízalo: estado actual, decisiones importantes (con su porqué) y errores a evitar.
- Mantenlo breve (máximo ~50 líneas): resume o elimina lo que ya no aporte.
- Si algo se convierte en una regla permanente, propón moverlo aquí en lugar de dejarlo en la memoria.
- No guardes nunca datos sensibles (claves, tokens, datos personales).

## Límites
- ✅ Siempre: actualizar `MEMORY.md` al terminar cada tarea; verificar JWT y RLS.
- ⚠️ Pregunta antes: dependencias nuevas, archivos nuevos, cambios en formato de datos.
- 🚫 Nunca: secretos en Git, saltarse RLS, editar el bloque reflex managed, hacer commit y push.

## Verificación
- `uv run pytest` y `uv run ruff check .` pasan; `uv run reflex run` abre; `/api/health` responde `{"status":"ok"}`.
