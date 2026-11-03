"""Pruebas de la ruta de salud de la API."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Chatly.backend.api.routes.health import router as health_router


def _client() -> TestClient:
    """Crear un cliente de pruebas con la ruta de salud montada."""
    api_app = FastAPI()
    api_app.include_router(health_router)
    return TestClient(api_app)


def test_health_returns_ok():
    """La ruta /api/health responde 200 con estado ok."""
    response = _client().get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
