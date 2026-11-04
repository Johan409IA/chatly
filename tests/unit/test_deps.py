"""Pruebas de la dependencia `require_actor` de la API."""

from typing import Annotated
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from Chatly.backend.api.deps import require_actor
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


@pytest.fixture
def stub(monkeypatch) -> _StubVerifier:
    import Chatly.backend.api.deps as deps

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
