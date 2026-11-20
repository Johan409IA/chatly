"""Ruta de salud de la API de Chatly."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Comprobar que la API de Chatly está disponible."""
    return {"status": "ok"}
