"""Pruebas del endpoint público del catálogo de intereses.

Patrón de `tests/unit/test_health.py`: app mínima con el router y un doble del
repositorio de intereses inyectado por `dependency_overrides`. Sin base de
datos ni red.
"""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Chatly.backend.api.routes.interests import (
    get_interest_repository_dep,
)
from Chatly.backend.api.routes.interests import (
    router as interests_router,
)
from Chatly.backend.schemas.interests import InterestCategoryDTO, InterestItemDTO


class _FakeInterestRepository:
    """Doble del repositorio: devuelve un catálogo fijo."""

    def __init__(self) -> None:
        self.category = InterestCategoryDTO(
            id=uuid4(),
            name="Tecnología",
            interests=[
                InterestItemDTO(id=uuid4(), name="Programación"),
                InterestItemDTO(id=uuid4(), name="IA"),
            ],
        )

    async def list_catalog(self) -> list[InterestCategoryDTO]:
        return [self.category]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(interests_router)
    app.dependency_overrides[get_interest_repository_dep] = lambda: _FakeInterestRepository()
    return TestClient(app)


def test_catalogo_devuelve_las_categorias() -> None:
    response = _client().get("/api/interests")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Tecnología"
    assert [item["name"] for item in body[0]["interests"]] == ["Programación", "IA"]
    assert body[0]["id"]
    assert body[0]["interests"][0]["id"]


def test_catalogo_es_cacheable() -> None:
    """El contrato §16.2 exige `Cache-Control: public, max-age=3600`."""
    response = _client().get("/api/interests")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_catalogo_no_exige_sesion() -> None:
    """El registro lo consume sin cookies: la ruta es pública."""
    response = _client().get("/api/interests")

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
