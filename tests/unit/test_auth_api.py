"""Pruebas de los endpoints de autenticación (`backend/api/routes/auth.py`).

Patrón de `tests/unit/test_deps.py`: app mínima con los handlers del
repertorio, doble del cliente de Supabase mediante `dependency_overrides` y
verificador JWT falso. Sin red ni Supabase real.
"""

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from Chatly.backend.api.routes.auth import router as auth_router
from Chatly.backend.core.errors import (
    DomainError,
    ErrorCode,
    domain_error_handler,
    validation_exception_handler,
)
from Chatly.backend.core.jwt import Actor
from Chatly.backend.services import auth_service as auth_service_module
from Chatly.backend.services.auth_service import AuthService, get_auth_service

_ACTOR_ID = uuid4()
_ACCESS_TOKEN = "token-de-acceso"
_REFRESH_TOKEN = "token-de-refresco"

_REGISTER_PAYLOAD = {
    "email": "  Johan@Example.COM ",
    "password": "Contra$ena1",
    "alias": "Johan_Dev",
    "display_name": "Johan Castillón",
    "birth_date": str(date.today() - timedelta(days=365 * 25)),
    "gender": "masculino",
}


class _StubVerifier:
    """Verificador JWT falso: solo acepta el access token de prueba."""

    def verify(self, token: str) -> Actor:
        if token != _ACCESS_TOKEN:
            raise jwt.InvalidTokenError("token de prueba inválido")
        return Actor(id=_ACTOR_ID)


class _FakeProfileRepository:
    """Doble del repositorio de perfiles: sin base de datos."""

    def __init__(self) -> None:
        self.aliases: set[str] = set()
        self.profiles: dict[str, Any] = {}

    async def alias_exists(self, alias: str) -> bool:
        return alias in self.aliases

    async def create_profile(self, **data: Any) -> None:
        self.aliases.add(data["alias"])
        self.profiles[data["user_id"]] = data

    async def get_profile(self, user_id: str) -> Any:
        data = self.profiles.get(user_id)
        if data is None:
            return None
        return type("Profile", (), {"alias": data["alias"], "display_name": data["display_name"]})()


class _FakeSupabaseClient:
    """Doble del cliente REST de Supabase Auth con respuestas del contrato."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.error_to_raise: DomainError | None = None
        self.tokens_response: dict[str, Any] = {
            "access_token": _ACCESS_TOKEN,
            "refresh_token": _REFRESH_TOKEN,
            "expires_in": 600,
            "user": {"id": str(_ACTOR_ID), "email_confirmed_at": "2026-01-01T00:00:00Z"},
        }

    async def _maybe_fail(self) -> None:
        if self.error_to_raise is not None:
            raise self.error_to_raise

    async def sign_up(
        self, email: str, password: str, redirect_to: str | None = None
    ) -> str:
        self.calls.append("sign_up")
        await self._maybe_fail()
        return "id-de-supabase"

    async def sign_in(self, email: str, password: str) -> dict[str, Any]:
        self.calls.append("sign_in")
        await self._maybe_fail()
        return self.tokens_response

    async def refresh_session(self, refresh_token: str) -> dict[str, Any]:
        self.calls.append("refresh_session")
        return self.tokens_response

    async def sign_out(self, access_token: str) -> None:
        self.calls.append("sign_out")

    async def resend_signup(self, email: str) -> None:
        self.calls.append("resend_signup")
        await self._maybe_fail()

    async def recover(self, email: str) -> None:
        self.calls.append("recover")
        await self._maybe_fail()

    async def update_password(self, token: str, password: str) -> None:
        self.calls.append("update_password")
        await self._maybe_fail()

    async def verify_signup(
        self, token_hash: str, verify_type: str = "signup"
    ) -> dict[str, Any]:
        self.calls.append("verify_signup")
        await self._maybe_fail()
        return {}

    async def exchange_code(self, code: str) -> dict[str, Any]:
        self.calls.append("exchange_code")
        await self._maybe_fail()
        return {}


@pytest.fixture
def fake_client(monkeypatch) -> _FakeSupabaseClient:
    """Doble de Supabase + verificador JWT, inyectados en el servicio."""
    fake = _FakeSupabaseClient()
    profiles = _FakeProfileRepository()
    monkeypatch.setattr(auth_service_module, "get_supabase_auth_client", lambda: fake)
    monkeypatch.setattr(auth_service_module, "get_jwt_verifier", lambda: _StubVerifier())

    service = AuthService(fake, profiles)
    monkeypatch.setattr(auth_service_module, "get_auth_service", lambda: service)
    client_profiles = profiles

    app = FastAPI()
    app.include_router(auth_router)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.dependency_overrides[get_auth_service] = lambda: service

    client = TestClient(app, raise_server_exceptions=False)
    client.fake = fake  # type: ignore[attr-defined]
    client.profiles = client_profiles  # type: ignore[attr-defined]
    yield client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------- registro


def test_registro_exitoso_normaliza_y_responde_201(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/register", json=_REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "verification_required"
    assert body["email"] == "johan@example.com"
    assert body["user_id"] == "id-de-supabase"
    assert fake_client.fake.calls == ["sign_up"]  # type: ignore[attr-defined]


def test_registro_con_contrasena_debil_responde_weak_password(fake_client: TestClient) -> None:
    payload = {**_REGISTER_PAYLOAD, "password": "debil"}
    response = fake_client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"


def test_registro_con_alias_corto_responde_validation_error(fake_client: TestClient) -> None:
    payload = {**_REGISTER_PAYLOAD, "alias": "aa"}
    response = fake_client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_registro_menor_de_edad_responde_422(fake_client: TestClient) -> None:
    payload = {**_REGISTER_PAYLOAD, "birth_date": str(date.today() - timedelta(days=365 * 10))}
    response = fake_client.post("/api/auth/register", json=payload)

    assert response.status_code == 422


def test_registro_persiste_el_perfil(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/register", json=_REGISTER_PAYLOAD)

    assert response.status_code == 201
    profile = fake_client.profiles.profiles["id-de-supabase"]  # type: ignore[attr-defined]
    assert profile["alias"] == "johan_dev"
    assert profile["display_name"] == "Johan Castillón"
    assert profile["gender"] == "masculino"


def test_registro_con_alias_ocupado_responde_409_sin_crear_cuenta(
    fake_client: TestClient,
) -> None:
    fake_client.profiles.aliases.add("johan_dev")  # type: ignore[attr-defined]
    response = fake_client.post("/api/auth/register", json=_REGISTER_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "alias_taken"
    assert fake_client.fake.calls == []  # type: ignore[attr-defined]


def test_registro_con_correo_repetido_responde_409(fake_client: TestClient) -> None:
    fake_client.fake.error_to_raise = DomainError(  # type: ignore[attr-defined]
        ErrorCode.EMAIL_ALREADY_REGISTERED,
        "Este correo ya está registrado.",
        status_code=409,
    )
    response = fake_client.post("/api/auth/register", json=_REGISTER_PAYLOAD)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


# ------------------------------------------------------------------------ login


def test_login_exitoso_fija_cookies_http_only(fake_client: TestClient) -> None:
    response = fake_client.post(
        "/api/auth/login", json={"email": "johan@example.com", "password": "Contra$ena1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] == _ACCESS_TOKEN
    assert body["user"]["id"] == str(_ACTOR_ID)
    assert body["user"]["email_verified"] is True
    cookies = response.headers.get("set-cookie", "")
    assert "chatly_at=token-de-acceso" in cookies
    assert "chatly_rt=token-de-refresco" in cookies
    assert "HttpOnly" in cookies


def test_login_con_credenciales_invalidas_responde_401(fake_client: TestClient) -> None:
    fake_client.fake.error_to_raise = DomainError(  # type: ignore[attr-defined]
        ErrorCode.INVALID_CREDENTIALS,
        "Correo o contraseña incorrectos.",
        status_code=401,
    )
    response = fake_client.post(
        "/api/auth/login", json={"email": "johan@example.com", "password": "OtraClave$1"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_sin_correo_confirmado_responde_403(fake_client: TestClient) -> None:
    fake_client.fake.error_to_raise = DomainError(  # type: ignore[attr-defined]
        ErrorCode.EMAIL_NOT_VERIFIED,
        "Confirma tu correo para poder entrar.",
        status_code=403,
    )
    response = fake_client.post(
        "/api/auth/login", json={"email": "johan@example.com", "password": "Contra$ena1"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


# ---------------------------------------------------------------------- refresh


def test_refresh_con_cookie_rota_el_token(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/refresh", cookies={"chatly_rt": _REFRESH_TOKEN})

    assert response.status_code == 200
    assert response.json()["access_token"] == _ACCESS_TOKEN
    assert "chatly_at=token-de-acceso" in response.headers.get("set-cookie", "")


def test_refresh_sin_cookie_responde_401(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


# ------------------------------------------------------------------------ otros


def test_logout_borra_las_cookies(fake_client: TestClient) -> None:
    response = fake_client.post(
        "/api/auth/logout",
        cookies={"chatly_at": _ACCESS_TOKEN, "chatly_rt": _REFRESH_TOKEN},
    )

    assert response.status_code == 204
    cookies = response.headers.get("set-cookie", "")
    assert 'chatly_at=""' in cookies
    assert 'chatly_rt=""' in cookies


def test_reenvio_responde_202_aun_cuando_supabase_falla(fake_client: TestClient) -> None:
    fake_client.fake.error_to_raise = ValueError("no disponible")  # type: ignore[attr-defined]
    response = fake_client.post(
        "/api/auth/resend-verification", json={"email": "quien@example.com"}
    )

    assert response.status_code == 202


def test_recuperacion_responde_202_siempre(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/forgot-password", json={"email": "johan@example.com"})

    assert response.status_code == 202


def test_restablecer_contrasena_debil_responde_weak_password(fake_client: TestClient) -> None:
    response = fake_client.post(
        "/api/auth/reset-password", json={"token": "t", "password": "debil"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"


def test_confirmar_con_token_hash_responde_204(fake_client: TestClient) -> None:
    response = fake_client.post(
        "/api/auth/confirm", json={"token_hash": "hash-de-prueba", "type": "signup"}
    )

    assert response.status_code == 204
    assert fake_client.fake.calls[-1] == "verify_signup"  # type: ignore[attr-defined]


def test_confirmar_con_codigo_pkce_responde_204(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/confirm", json={"code": "codigo-pkce"})

    assert response.status_code == 204
    assert fake_client.fake.calls[-1] == "exchange_code"  # type: ignore[attr-defined]


def test_confirmar_sin_token_responde_422(fake_client: TestClient) -> None:
    response = fake_client.post("/api/auth/confirm", json={})

    assert response.status_code == 422
