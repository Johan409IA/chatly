"""Verificación de JWT de Supabase Auth mediante claves públicas (JWKS).

Sigue `docs/architecture.md` §5.2:

- Claves públicas desde `SUPABASE_JWKS_URL` con `PyJWKClient` y caché en proceso.
- Validaciones: firma, `alg` permitido, `iss`, `aud`, `exp`, `iat` y `sub`.
- El actor es `sub` (UUID). El estado de confirmación de correo no se asume
  desde el JWT: se consultará `profiles.email_verified_at`.
- Resultado cacheado por digest del token para no verificar en cada evento.

No registra el contenido del token ni de los claims en los logs.
"""

import hashlib
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from jwt import PyJWK, PyJWKClient

from Chatly.backend.core.settings import get_settings

ALLOWED_ALGORITHMS = ["ES256", "RS256"]
_CACHE_MAX_ENTRIES = 512


@dataclass(frozen=True)
class Actor:
    """Identidad derivada del JWT verificado; nunca del cliente."""

    id: UUID
    email: str | None = None
    session_id: str | None = None


class JWTVerifier:
    """Verificador de JWT de Supabase con caché de claves y de resultados."""

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audiences: list[str],
        *,
        leeway_seconds: int = 30,
        jwks_client: PyJWKClient | None = None,
    ) -> None:
        self._jwks_client = jwks_client or PyJWKClient(jwks_url)
        self.issuer = issuer
        self.audiences = audiences
        self.leeway_seconds = leeway_seconds
        self._cache: dict[str, tuple[Actor, int]] = {}
        self._lock = threading.Lock()

    def verify(self, token: str) -> Actor:
        """Verifica el token y devuelve el actor; lanza `jwt.PyJWTError`."""
        cache_key = hashlib.sha256(token.encode()).hexdigest()

        cached = self._cache.get(cache_key)
        if cached is not None and cached[1] > time.time():
            return cached[0]

        claims = self._decode(token)
        actor = Actor(
            id=UUID(claims["sub"]),
            email=claims.get("email"),
            session_id=claims.get("session_id"),
        )
        with self._lock:
            if len(self._cache) >= _CACHE_MAX_ENTRIES:
                self._evict_expired()
            self._cache[cache_key] = (actor, int(claims["exp"]))
        return actor

    def prime(self) -> None:
        """Descarga y cachea el JWKS por adelantado (warm-up de arranque).

        La descarga usa I/O síncrono (`urllib`): llamarlo fuera del event loop
        evita bloquearlo en la primera verificación. Si falla (sin red), la
        primera verificación real lo reintentará.
        """
        self._jwks_client.get_signing_keys()

    def _decode(self, token: str) -> dict:
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            issuer=self.issuer,
            audience=self.audiences,
            leeway=self.leeway_seconds,
            options={"require": ["exp", "iat", "sub"]},
        )

    def _evict_expired(self) -> None:
        now = int(time.time())
        for key, (_, exp) in list(self._cache.items()):
            if exp <= now:
                del self._cache[key]


class _StaticJWKClient:
    """Cliente JWKS fijo para pruebas: siempre devuelve la clave indicada."""

    def __init__(self, key: PyJWK) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, token: str) -> PyJWK:
        return self._key


def build_verifier_from_settings(*, jwks_client: PyJWKClient | None = None) -> JWTVerifier:
    """Crea el verificador con la configuración del entorno."""
    settings = get_settings()
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"
    return JWTVerifier(
        jwks_url=settings.supabase_jwks_url,
        issuer=issuer,
        audiences=allowed_audiences(settings.supabase_url),
        leeway_seconds=settings.jwt_leeway_seconds,
        jwks_client=jwks_client,
    )


def allowed_audiences(supabase_url: str) -> list[str]:
    """Audiencias válidas: `authenticated` y el ref del proyecto (JWT nuevos)."""
    project_ref = supabase_url.rstrip("/").removeprefix("https://").split(".")[0]
    return ["authenticated", project_ref]


@lru_cache
def get_jwt_verifier() -> JWTVerifier:
    """Devuelve el verificador de la aplicación (una instancia por proceso)."""
    return build_verifier_from_settings()
