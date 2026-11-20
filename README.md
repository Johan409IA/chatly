# Chatly

Chatly es una aplicación web responsive de mensajería en español. La interfaz,
las rutas del API y el servidor web se ejecutan con Node.js y Next.js.

## Requisitos

- Node.js `>=20.9` (recomendado: Node.js 22)
- npm
- Supabase Auth y una base de datos PostgreSQL con el esquema de Chatly

## Instalación

Instala las dependencias:

```sh
npm ci
```

Copia la plantilla de variables de entorno:

```powershell
Copy-Item .env.example .env
```

Configura en `.env`:

- `APP_DATABASE_URL`: URL PostgreSQL del rol de aplicación `chatly_app`, sin
  `BYPASSRLS` (formato `postgresql://...`).
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` y `SUPABASE_JWKS_URL`: valores del
  proyecto Supabase.
- `FRONTEND_URL`: origen de la aplicación para los enlaces de autenticación.

No compartas ni publiques `.env` o sus credenciales.

## Desarrollo

```sh
npm run dev
```

Abre `http://localhost:3000`. Las pruebas, el lint y la compilación se ejecutan
con:

```sh
npm test
npm run lint
npm run build
```

Para iniciar la compilación de producción localmente, usa `npm start`.

## Funcionalidad disponible

- Registro con verificación de correo, inicio de sesión y recuperación de
  contraseña mediante Supabase Auth.
- Selección de intereses y consulta/actualización del perfil.
- Bandeja de conversaciones, historial, envío de mensajes y confirmación de
  lectura conectados a las rutas de Next.js.

Las capacidades que todavía no expone el backend Node no se simulan en la
interfaz.

## Esquema de base de datos

La aplicación Node necesita que el esquema existente de Chatly esté aplicado
en PostgreSQL. Las migraciones históricas aún están en Alembic y no se ejecutan
desde el servidor Node ni desde la imagen Docker; por ahora, cualquier cambio
de esquema debe aplicarse mediante el proceso de migración existente antes del
despliegue. Portar esas migraciones a Node sigue pendiente.

## Despliegue

La imagen Docker construye la aplicación Next.js en modo standalone y arranca
el servidor Node en el puerto indicado por `PORT` (3000 por defecto). Configura
en el proveedor de despliegue las mismas variables de entorno que en `.env`.
El workflow de GitHub Actions ejecuta `npm ci`, lint, pruebas y compilación.
