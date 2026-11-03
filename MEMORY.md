# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- Fase 0 completa y verificada. Ramas `main` y `develop` publicadas en GitHub.
- `/api/health` responde `{"status":"ok"}`; `@supabase/supabase-js` declarado en `rxconfig.py`.
- `uv sync`, `uv run reflex run`, `uv run pytest` (2 tests) y `uv run ruff check .` pasan.
- Proyecto Supabase Cloud ya creado (URL/keys en lugar seguro, no en el repo).

## Decisiones (y por qué)
- Sin CI/CD en GitHub y sin protección de `main` — decisión del equipo; la verificación es local.
- `bunfig.toml` apunta al espejo npmmirror porque la red local bloquea `registry.npmjs.org` (TLS/403).
- `pythonpath = ["."]` en pytest para importar el módulo `Chatly` desde tests.
- Ruff `target-version = py312` aunque el proyecto usa Python 3.13.7.

## Aprendizajes y errores a evitar
- El bloque `reflex managed` de `AGENTS.md` no se edita; el contenido propio va después de los marcadores.
- `uv run reflex run` regenera `.web`; conservar `bunfig.toml` en `.web` para que la instalación frontend no falle.
- No asumir que `auth.uid()` llega solo con conexión PostgreSQL directa: establecer contexto por transacción.

## Próximos pasos
- Fase 1: configuración central (Pydantic Settings), engine SQLAlchemy async + pool, Psycopg 3 a Supabase Session Pooler, `target_metadata` de Alembic y prueba de aislamiento RLS entre transacciones.
- Añadir modelos base (UUID, timestamps, soft delete, auditoría) y manejo centralizado de errores.
