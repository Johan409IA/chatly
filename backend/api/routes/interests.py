"""Endpoint público del catálogo de intereses (`docs/api-contracts.md` §16.2).

Es el único endpoint social público: el registro lo consume antes de que
exista sesión (Q15, Q128). Se sirve cacheable porque el catálogo solo cambia
con las migraciones.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from Chatly.backend.repositories.interest_repository import (
    InterestRepository,
    get_interest_repository,
)
from Chatly.backend.schemas.interests import InterestCategoryDTO

router = APIRouter(tags=["interests"])

CACHE_CONTROL = "public, max-age=3600"


def get_interest_repository_dep() -> InterestRepository:
    """Dependencia FastAPI: repositorio de intereses (sustituible en pruebas)."""
    return get_interest_repository()


InterestRepositoryDep = Annotated[InterestRepository, Depends(get_interest_repository_dep)]


@router.get("/api/interests", response_model=list[InterestCategoryDTO])
async def list_interests(
    response: Response,
    repository: InterestRepositoryDep,
) -> list[InterestCategoryDTO]:
    """Categorías activas del catálogo con sus intereses."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    return await repository.list_catalog()
