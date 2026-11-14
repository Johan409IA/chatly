# Chatly

Chatly es una aplicación web responsive de mensajería en español, diseñada para facilitar conversaciones privadas y grupales y ayudar a sus participantes a tomar decisiones mediante encuestas. Incluye además una sección social para descubrir personas y grupos afines mediante intereses compartidos. Se puede instalar como PWA y ofrece capacidades offline progresivas.

## Funcionalidades

- **Perfiles y descubrimiento de personas:** registro con verificación de correo, perfil con nombre visible, alias único y fotografía; búsqueda por alias o correo sin revelar el correo en los resultados.
- **Intereses personales y sugerencias de personas:** catálogo predefinido de intereses organizado por categorías, con un máximo de 10 por usuario y selección opcional durante el registro. La sección Descubrir sugiere personas ordenadas por intereses coincidentes y muestra fotografía, nombre visible e intereses compartidos. El perfil tiene visibilidad pública activable, independiente de la visibilidad de los grupos.
- **Grupos descubribles y solicitudes de unión:** los grupos se crean privados; su administrador puede marcarlos como descubribles y asignarles de 1 a 5 intereses. Descubrir permite buscar grupos por nombre y recomienda los que comparten intereses, indicando plazas disponibles. Cualquier usuario verificado puede enviar una solicitud de incorporación (solo una pendiente a la vez), que el administrador aprueba o rechaza, con notificaciones internas.
- **Conversaciones privadas y grupales:** un chat privado único por pareja; grupos de hasta 10 personas, con administración, gestión de integrantes e historial sujeto a los periodos de membresía.
- **Mensajería:** envío de texto, edición y eliminación de mensajes propios, respuestas, reacciones con un conjunto definido de emojis y confirmaciones de lectura.
- **Encuestas:** creación de encuestas en conversaciones, votación de una opción por persona, cambio de voto mientras estén abiertas y resultados en tiempo real.
- **Actualizaciones en tiempo real:** presencia en línea, indicador de escritura, mensajes, reacciones, votos y contador de mensajes no leídos.
- **Uso offline progresivo:** consulta de conversaciones y mensajes almacenados, redacción de mensajes sin conexión y sincronización al recuperar la conexión.
- **Trazabilidad:** registro interno de operaciones importantes y conservación del historial conforme a las reglas de cada conversación.

**Estado actual:** están implementados el registro con verificación de correo por Supabase Auth, el inicio de sesión, la selección opcional de intereses y la base de perfiles. Conversaciones, mensajería, encuestas y descubrimiento social siguen en desarrollo.

## Requisitos

- Python `>=3.13,<3.14`
- [uv](https://docs.astral.sh/uv/)
- Una configuración de Supabase para la base de datos y los servicios de autenticación, Realtime y Storage.

## Clonar el repositorio

```sh
git clone https://github.com/Johan409IA/chatly.git
cd chatly
```

## Instalación y configuración

Instala las dependencias del proyecto:

```sh
uv sync
```

Crea el archivo local de variables de entorno a partir de la plantilla:

```sh
# macOS / Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Configura en `.env` los valores de Supabase indicados en `.env.example`. No compartas ese archivo ni publiques sus credenciales.

### Conexiones a la base de datos

El `.env` usa tres conexiones con roles distintos:

- `DATABASE_URL`: rol administrativo (`postgres`), solo para DDL y migraciones.
- `APP_DATABASE_URL`: rol de aplicación `chatly_app` (sin `BYPASSRLS`), para el runtime.
- `TEST_DATABASE_URL`: rol de aplicación para las pruebas de RLS.

En el Session Pooler el usuario debe escribirse como `rol.project_ref` y la contraseña ir codificada en la URL.

### Migraciones

El esquema propio de Chatly lo administra Alembic; no dupliques estas tablas con el Supabase CLI. Aplica las migraciones con el rol administrativo:

```sh
uv run alembic upgrade head
```

Sin ellas el backend no encuentra las tablas y algunas pruebas se omiten. Para revertir la última migración:

```sh
uv run alembic downgrade -1
```

### Supabase Auth

- Configura SMTP (Brevo) en Supabase Auth para la confirmación de correo y la recuperación de contraseña.
- Añade a las Redirect URLs la ruta de confirmación de la app: `http://localhost:3000/auth/confirm` y, en producción, `https://chatly-3lh3.onrender.com/auth/confirm`. El backend la construye a partir de `FRONTEND_URL` (en Render se deriva de `RENDER_EXTERNAL_URL`). Configura también esa URL como **Site URL** para que los enlaces de recuperación apunten a la app desplegada.
- Personaliza la plantilla «Reset password» en Supabase Auth con el flujo `token_hash`, para que el enlace aterrice en la app y el backend canjee el token:

  ```html
  <a href="{{ .SiteURL }}/reset-password?token_hash={{ .TokenHash }}&type=recovery">Restablecer contraseña</a>
  ```

## Ejecución en desarrollo

```sh
uv run reflex run
```

La interfaz queda en `http://localhost:3000` y el API en `http://localhost:8000`; puedes comprobar el backend con `http://localhost:8000/api/health`.

En Windows, `uv sync` instala `winloop` (grupo `dev`, solo `win32`) y granian lo
detecta automáticamente; así psycopg async usa un bucle de eventos compatible.
No definas `NODE_ENV=production` de forma global: en desarrollo Vite y React
necesitan el runtime de desarrollo (`NODE_ENV=development`, que es el valor por
defecto cuando la variable no existe). En este proyecto la variable que lee la
aplicación es `APP_ENV`.

## Despliegue en producción (Render)

La app corre en **https://chatly-3lh3.onrender.com** como servicio web Docker
(plan Free) dentro del proyecto `chatly` de Render, sobre la rama `main`.

- `Dockerfile`: imagen de un solo contenedor. En el build exporta el frontend
  con Bun y, al arrancar, aplica `alembic upgrade head`, levanta Caddy (puerto
  `$PORT`, 10000 por defecto) y redis, y ejecuta `reflex run --env prod`.
- `Caddyfile`: sirve el frontend estático desde `/srv` y hace proxy de
  `/_event/*`, `/ping`, `/_health`, `/_upload*` y `/api/*` al backend (`:8000`).
- `.dockerignore`: excluye `.web`, `.venv`, `.env`, `docs/` y `tests/` del build.
- `requirements.txt`: se regenera con
  `uv export --no-dev --no-emit-project --no-hashes --format requirements-txt -o requirements.txt`.
- Variables de entorno: se configuran en Render (servicio → Environment) con los
  valores de producción. `FRONTEND_URL`, `API_PUBLIC_URL` y `CORS_ORIGINS` se
  derivan de `RENDER_EXTERNAL_URL` en `settings.py`, así que sobreviven a
  cambios de dominio. `API_PUBLIC_URL` queda vacío: el navegador llama al API en
  el mismo origen.
- Auto-deploy: cada push o merge a `main` reconstruye y despliega. El workflow
  `CI` (`.github/workflows/ci.yml`) ejecuta ruff, tests unitarios y
  `reflex compile --dry` en cada push a `main`/`develop` y en pull requests.

Notas del plan Free: el servicio se duerme tras 15 minutos sin tráfico (la
siguiente petición tarda ~1 minuto en despertarlo) y no envía SMTP saliente; los
correos los envía Supabase.

## Tests

```sh
# Pruebas unitarias
uv run pytest tests/unit

# Pruebas de integración (requieren Supabase y red; el marcador es `db`)
uv run pytest tests/integration

# Lint y formato
uv run ruff check .
uv run ruff format .
```

## Documentación

- [Diseño funcional de Chatly](docs/chatly.md): reglas, funcionalidades, casos límite y decisiones tecnológicas.
- [Arquitectura](docs/architecture.md)
- [Esquema de base de datos](docs/database-schema.md)
- [Contratos de API](docs/api-contracts.md)
- [Eventos en tiempo real](docs/realtime-events.md)
- [Matriz de autorización](docs/authorization-matrix.md)
- [Roadmap](docs/roadmap.md)
