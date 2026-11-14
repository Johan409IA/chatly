# Despliegue en un solo contenedor para Render: Caddy sirve el frontend
# exportado y hace proxy de las rutas del backend desde un único puerto.
# TLS se termina en el borde de Render.

ARG PORT=10000
ARG API_URL

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
COPY --from=oven/bun:1 /usr/local/bin/bun /usr/local/bin/bun
ENV UV_COMPILE_BYTECODE=1 UV_NO_CACHE=1 PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY requirements.txt .
RUN uv venv && uv pip install -r requirements.txt

COPY . .

ARG PORT API_URL
# El export importa la app y valida la configuración: estos marcadores solo
# satisfacen esa validación en tiempo de build. Los valores reales llegan por
# variables de entorno al arrancar el contenedor (nunca se guardan en la imagen).
# `API_PUBLIC_URL` vacío compila el frontend para llamar al API en el mismo origen.
RUN --mount=type=cache,target=/root/.bun/install/cache \
    API_PUBLIC_URL="" \
    DATABASE_URL="postgresql+psycopg://build:build@localhost:5432/build" \
    APP_DATABASE_URL="postgresql+psycopg://build:build@localhost:5432/build" \
    TEST_DATABASE_URL="postgresql+psycopg://build:build@localhost:5432/build" \
    SUPABASE_URL="https://build.invalid" \
    SUPABASE_PUBLISHABLE_KEY="build" \
    SUPABASE_JWKS_URL="https://build.invalid/.well-known/jwks.json" \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} reflex export --frontend-only --no-zip

FROM python:3.13-slim

RUN apt-get update -y && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*
COPY --from=caddy:2 /usr/bin/caddy /usr/bin/caddy

ARG PORT
ENV PATH="/app/.venv/bin:$PATH" PORT=$PORT REFLEX_REDIS_URL=redis://localhost PYTHONUNBUFFERED=1

WORKDIR /app
# El usuario necesita ser dueño de /app para que reflex cree .states; Caddy y
# redis escriben en su HOME/workdir, que resuelven a /app.
RUN adduser --disabled-password --gecos "" --home /app reflex && chown reflex /app
COPY --chown=reflex --from=builder /app/.venv .venv
COPY --chown=reflex --from=builder /app/.web/backend .web/backend
COPY --from=builder /app/.web/build/client /srv
COPY --chown=reflex . .
USER reflex

EXPOSE $PORT

# Aplica las migraciones antes de arrancar; si fallan, el contenedor no inicia.
CMD if [ -d migrations ]; then reflex db migrate; fi && \
    caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
