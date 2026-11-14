"""DTOs del catálogo de intereses (`docs/api-contracts.md` §16.1).

Los nombres de campo van en inglés porque son parte del contrato público
(`InterestCategory`); las tablas y columnas de la base de datos van en
español (AGENTS.md).
"""

from uuid import UUID

from pydantic import BaseModel, Field


class InterestItemDTO(BaseModel):
    """Un interés concreto del catálogo."""

    id: UUID
    name: str


class InterestCategoryDTO(BaseModel):
    """Una categoría del catálogo con los intereses que la componen."""

    id: UUID
    name: str
    interests: list[InterestItemDTO] = Field(default_factory=list)
