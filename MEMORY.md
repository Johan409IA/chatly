# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- **Desplegada en Render (2026-11-26)**: https://chatly-3lh3.onrender.com (Docker, Free, auto-deploy desde `main`). `/api/health`, `/api/interests`, `/login`, `/register` verificados. `.css` de `assets/` NO admite encabezado `#` (lightningcss): usar `/* */`.
- **Hotfix crítico (2026-11-26, PRs #20/#21, deploy `aaa74f9` en main)**: el frontend de conversaciones (commit `7fff538`) llegó con `self._parse_response`, un método que nunca existió en `ConversationState` → cada carga de `/` fallaba con `AttributeError` y Reflex mostraba el aviso genérico en inglés «An error occurred». Fix: usar la función `parse_response` importada de `api_client`. **Lección: aviso genérico de Reflex en inglés = excepción en un event handler; buscar `[Reflex Backend Exception]` en los logs de Render.** Guarda de regresión en `tests/unit/test_conversation_state.py` (ningún handler puede llamar a un `self._*` no definido). 139 unitarias en verde.
- **Iteración 4 en `feature/chat-messaging` (2026-11-26, PR #18 a develop)**: API de mensajes §7.2.1/§8 completa — `MessageRepository` (repo-enforces, sin service), `GET/POST /api/conversations/{id}/messages` (cursor 50/30, orden estable `(creado_en,id)`, idempotencia por `(autor_id, id_mensaje_cliente)`) y `POST /api/messages/direct` (crea conversación+membresías+mensaje en una transacción; 201/200). **HALLAZGO: el router de chat NO estaba montado en `Chatly.py`** (solo health/auth/interests/profile): `GET /api/conversations` daba 404 en producción; montado en este PR. Sin migración nueva (0004 + 0007 ya cubren tabla, índices y RLS). 21 tests nuevos; 136 unitarias en verde.
- **Frontend de mensajes en el mismo PR**: botón «Cargar mensajes anteriores» (botón explícito, no scroll-infinito), responder con chip + cita en burbuja, envío optimista con reloj «Enviando…» y ✓ al confirmar. `ConversationState` con `cursor_created_at/cursor_id`, `reply_to_*`, `pending_message`.
- **Chats nuevos desde el buscador (2026-11-26, PRs #22/#23, deploy `48d6c2d`)**: escribir 2+ caracteres consulta `GET /api/users/search` y muestra la sección PERSONAS; al elegir a alguien, `POST /api/conversations/direct` reutiliza el chat o entra en modo temporal («Chat nuevo: el primer mensaje inicia la conversación») y el envío va por `POST /api/messages/direct`, que crea la conversación y refresca la bandeja. Sin backend nuevo: `select_user`/`handle_select_user_result`/`handle_send_result` con `request_id` = destinatario.
- **Fix RLS chat directo (2026-11-26, PRs #24/#25, migración `0014_rls_chat_directo`, deploy `ce72a38`)**: el primer mensaje fallaba con 42501 en `conversaciones`. Tres causas: (1) la política `conversaciones_insert_backend` de 0007 evaluaba falso SOLO en el INSERT pese a cumplirse (recrearla con el mismo texto la arregló — interna corrupta por funciones `app.*` redefinidas después); (2) `RETURNING id` sobre `conversaciones` exige pasar la política SELECT (`has_membership`), imposible sin membresías → el repositorio genera el `id` en la app y sin RETURNING (también en `create_group`, roto igual); (3) `miembros_insert_backend` no cubría la membresía del destinatario → `app.can_seed_direct_membership` (pareja registrada, <2 integrantes). Flujo completo verificado contra la BD real con rollback. **Lecciones: el aviso genérico de error escondía esto; diagnosticar RLS con scripts psycopg directos al pooler (`APP_DATABASE_URL` del .env local) y `set_config('app.current_user_id', uid, true)` en la misma transacción; si una política "imposible" falla, recrearla; revisar que `RETURNING` pase también la política SELECT; NUNCA dejar políticas `check(true)` de diagnóstico en producción (drop se revierte con la transacción fallida).**
- **Diseño unificado (skill design-taste-frontend)**: acento del chat `#3d8bff` y gradiente del botón de auth (`#4a93ff→#1f6beb`); violetas propios del chat sustituidos por azules (los del panel de marca de auth se conservan). Intereses y género seleccionados en el registro: fondo azul sólido + anillo + glow doble + escala + badge ✓ (verificado en Playwright a 1280 y 390). `prefers-reduced-motion` respetado.
- **Interfaz de chat oscura (2026-11-26, rama `feature/interfaz-chat-oscura`)**: `assets/chat.css` reescrito como cuatro paneles de cristal sobre fondo nocturno; red de nodos SVG decorativa en el panel central (`_network_backdrop` en `chat_interface.py`, `aria-hidden`) con pulso CSS y `prefers-reduced-motion`; compositor de 24 px con anillo de foco azul, burbujas e info oscuras. Los inputs de Radix exponen su clase en el wrapper: estilizar `input`/`textarea` internos. Verificado con Playwright CLI a 1375/1024/768/390/320 sin overflow; 139 tests y ruff en verde.
- **Pendiente de la Iteración 4**: E2E del chat con dos cuentas reales verificadas (envío, ✓, respuesta, paginación >50 mensajes); revisión cruzada del PR; merge a `main`.
- Iteraciones 1–3 completadas (auth, perfiles, intereses, conversaciones, grupos, solicitudes; `alembic_version = 0013_descubrimiento_social`).
- Pendientes globales: 0014_social_cron (pg_cron), endpoints §16.6/16.7 y Descubrir (Iteración 8), lecturas §7.10 (Iteración 5), middleware de rate limit (§14), probar recuperación con correo real.

## Decisiones (y por qué)
- Tres conexiones: `DATABASE_URL` (DDL), `APP_DATABASE_URL` y `TEST_DATABASE_URL` (ambas `chatly_app` sin BYPASSRLS).
- Nombres en español para tablas/columnas; inglés para clases/funciones/variables.
- Límite de 4.000 lo aplica el repositorio → `message_too_long` (no `validation_error` genérico de Pydantic).
- Paginación hacia atrás: botón explícito (IntersectionObserver/JS custom se puede añadir después sin romper nada).
- El token `__GENERATE_UUID__` se sustituye por `crypto.randomUUID()` en el script de `fetch` (idempotencia generada en el navegador).
- Login/logout/refresh vía fetch HTTP (cookies HttpOnly); `rx.call_script` con expresión async; errores por campo como vars sueltas, no dict.
- El registro valida `interest_ids` antes de `sign_up`; el filtro `activo` vive en el SQL.
- No crear perfiles/datos de prueba sin permiso: `perfiles.id` tiene FK a `auth.users`.

## Aprendizajes y errores a evitar
- **El router puede existir y no estar montado**: verificar `api_app.include_router(...)` en `Chatly.py` al añadir rutas nuevas.
- Violación de RLS → `ProgrammingError` 42501; con RLS y sin GRANT la app recibe 42501, con GRANT y sin políticas 0 filas: van juntos por tabla.
- Un trigger que actualiza una tabla con RLS debe ser `SECURITY DEFINER` (si no, falla en silencio).
- I/O síncrono (JWKS, engine) bloquea granian: warm-up en lifespan + `asyncio.to_thread`.
- Windows: `winloop` en grupo dev (marker win32); no usar uvicorn; granian muere al recargar → reiniciar `uv run reflex run`.
- `reflex db migrate` exige `db_url` en rxconfig; la app usa Alembic (`alembic upgrade head` en el CMD de Docker).
- Los tests con dobles no ejercitan RLS ni constraints: verificar en vivo contra Supabase como `chatly_app`.
- En Windows `alembic upgrade --sql` necesita `PYTHONIOENCODING=utf-8`; Ruff B008 → `Annotated[T, Depends…]`; `pytest tests/unit` (integración se cuelga sin red).
- `rx.cond` no acepta `== False` (E712): usar `~var`.
- Plan Free de Render: cold start ~1 min tras 15 min sin tráfico.

## Próximos pasos
- Revisar y aprobar PR #18 → merge a `develop` → PR `develop` → `main` → verificar deploy en Render (`/api/health` + envío real entre dos cuentas).
- Iteración 5: edición/eliminación/versiones, reacciones, lecturas (`POST .../read`, ✓✓, no leídos), DTO con `reactions`/`read`.
- Iteración 8: Descubrir (§16), solicitudes, auditoría, límites de frecuencia.
- Pruebas E2E del chat (Playwright) cuando haya credenciales de prueba verificadas.
