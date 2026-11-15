"""Pruebas de las dependencias `require_actor` y `require_verified_actor`."""

from typing import Annotated
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from Chatly.backend.api import deps
from Chatly.backend.api.deps import require_actor, require_verified_actor
from Chatly.backend.core.errors import DomainError, domain_error_handler
from Chatly.backend.core.jwt import Actor


class _StubVerifier:
    def __init__(self) -> None:
        self.tokens_validos: dict[str, Actor] = {}

    def verify(self, token: str) -> Actor:
        actor = self.tokens_validos.get(token)
        if actor is None:
            raise jwt.InvalidTokenError("token de prueba inválido")
        return actor


class _StubProfileRepository:
    """Repositorio de perfiles falso: solo la comprobación de verificación."""

    def __init__(self, verified: bool = True) -> None:
        self.verified = verified
        self.calls = 0

    async def is_verified(self, user_id: str) -> bool:
        self.calls += 1
        return self.verified


@pytest.fixture
def stub(monkeypatch) -> _StubVerifier:
    stub = _StubVerifier()
    monkeypatch.setattr(deps, "get_jwt_verifier", lambda: stub)
    return stub


@pytest.fixture
def cliente(stub) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_handler)

    @app.get("/api/protegido")
    async def protegido(
        actor: Annotated[Actor, Depends(require_actor)],
    ) -> dict[str, str]:
        return {"actor_id": str(actor.id)}

    return TestClient(app, raise_server_exceptions=False)


def test_sin_token_responde_401_con_envelope(cliente) -> None:
    response = cliente.get("/api/protegido")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_bearer_valido_devuelve_el_actor(cliente, stub) -> None:
    actor_id = uuid4()
    token = "token-de-prueba"
    stub.tokens_validos[token] = Actor(id=actor_id)

    response = cliente.get("/api/protegido", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["actor_id"] == str(actor_id)


def test_cookie_chatly_at_valida_devuelve_el_actor(cliente, stub) -> None:
    actor_id = uuid4()
    token = "token-en-cookie"
    stub.tokens_validos[token] = Actor(id=actor_id)

    response = cliente.get("/api/protegido", cookies={"chatly_at": token})

    assert response.status_code == 200
    assert response.json()["actor_id"] == str(actor_id)


def test_bearer_invalido_responde_401(cliente) -> None:
    response = cliente.get("/api/protegido", headers={"Authorization": "Bearer no-valido"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


# ------------------------------------------------------ require_verified_actor


def _app_verificada(verified: bool) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(DomainError, domain_error_handler)
    repository = _StubProfileRepository(verified=verified)

    @app.get("/api/chat")
    async def chat(
        actor: Annotated[Actor, Depends(require_verified_actor)],
    ) -> dict[str, str]:
        return {"actor_id": str(actor.id)}

    app.dependency_overrides[deps.get_profile_repository_dep] = lambda: repository
    return app


@pytest.fixture
def cliente_verificado(stub) -> TestClient:
    return TestClient(_app_verificada(verified=True), raise_server_exceptions=False)


def test_actor_verificado_accede_al_recurso(cliente_verificado, stub) -> None:
    actor_id = uuid4()
    token = "token-verificado"
    stub.tokens_validos[token] = Actor(id=actor_id)

    response = cliente_verificado.get("/api/chat", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["actor_id"] == str(actor_id)


def test_actor_sin_confirmar_recibe_403_email_not_verified(stub) -> None:
    cliente = TestClient(_app_verificada(verified=False), raise_server_exceptions=False)
    token = "token-sin-confirmar"
    stub.tokens_validos[token] = Actor(id=uuid4())

    response = cliente.get("/api/chat", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


def test_verificacion_no_se_aplica_ante_un_token_invalido(cliente_verificado) -> None:
    """La verificación es posterior al JWT: sin sesión válida responde 401."""
    response = cliente_verificado.get("/api/chat", headers={"Authorization": "Bearer no-valido"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
