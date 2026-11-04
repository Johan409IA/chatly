# MEMORY.md — Chatly

Memoria del proyecto entre sesiones de agente. Máximo ~50 líneas.

## Estado actual
- **Iteración 1 (arquitectura de backend) completa y verificada** en `arquitectura-backend`.
- **Iteración 2, tareas 1–6 hechas** en `auth-email-verificacion` (sin commits): Supabase Auth con confirmación obligatoria, redirect URLs, SMTP Brevo, verificación JWT/JWKS y guardas de Reflex. Falta probar correos reales (tarea 3).
- JWT: `backend/core/jwt.py` (PyJWKClient, alg ES256/RS256, iss/aud/exp/iat/sub, leeway 30 s, caché por digest del token) + `backend/api/deps.py` (`require_actor`: cookie `chatly_at` o Bearer).
- Guardas: `Chatly/state/session_state.py` (`SessionState.guard_page` / `redirect_if_authenticated`); `/login` provisional en `pages/auth/login.py`. `require_verified` llega con la tabla `profiles`.
- Verificado: `pytest` 46 passed, `ruff check/format`, `reflex compile --dry`.

## Decisiones (y por qué)
- **Pruebas contra Supabase nube**, no Postgres local: sin Docker; desvío en `architecture.md` §11.
- **Dos conexiones de prueba**: admin (`DATABASE_URL`/`postgres`, solo DDL) y app (`TEST_DATABASE_URL`/`chatly_app`). `require_app_role()` falla si no es `chatly_app` o tiene BYPASSRLS.
- **`chatly_app` hereda de `authenticated`**: políticas llaman a `app.current_actor_id()` directo, sin helpers SECURITY DEFINER.
- **Nombres en español** para tablas/columnas (`creado_en`, `propietario_id`) y en inglés para clases/funciones.
- **Caché JWT por digest del token** (no session_id+exp): un token forjado no puede reutilizar el actor cacheado de otro usuario; mismo rendimiento.
- **Audience JWT**: se aceptan `authenticated` (legacy) y el project_ref (tokens nuevos), derivado de `SUPABASE_URL`.
- **Brevo Free: 300 correos/día** (reinicia a diario, no acumula); registrado en `architecture.md` §5.5 con el procedimiento de reenvío de confirmación.
- SelectorEventLoop en Windows (Psycopg 3 async); `set_config(..., true)` local a la transacción (imprescindible con pool).

## Aprendizajes y errores a evitar
- Reflex: cookies solo server-side con `self.router.headers.cookie`; `rx.Cookie` las expone al frontend.
- Reflex: un `@rx.page(route=...)` + `add_page` del mismo componente duplica la ruta (RouteValueError).
- Guardas de Reflex devuelven `rx.redirect(...)` desde `on_load`; `[]` continúa la carga.
- Ruff B008: usar `Annotated[Actor, Depends(require_actor)]`, no default `= Depends(...)`.
- `postgres` no puede otorgar `usage` del schema `auth`; la vía es la membresía en `authenticated`. Un rol NOINHERIT no hereda privilegios de sus grupos.
- Violación de RLS llega como `ProgrammingError` (SQLSTATE 42501), no `IntegrityError`. `DROP ROLE` exige revocar grants antes.
- `uv run reflex run` regenera `.web`; conservar `bunfig.toml`. No editar el bloque `reflex managed` de AGENTS.md.

## Próximos pasos
- Tarea 3: probar confirmación/recuperación con direcciones reales vía Brevo.
- Iteración 2: tablas `profiles`/`user_contacts` + RLS, sincronización de perfil al registrar, búsqueda exacta por correo sin exponerlo, alias único (3–20, cambio cada 30 días), pantallas y pruebas negativas.
- Cuando la app corra sin DDL, mover `DATABASE_URL` a `chatly_app` y dejar una URL separada solo para migraciones.
