"""Repositorio del catálogo de intereses y de la selección personal.

El catálogo se lee con `app.catalogo_intereses()`, función `SECURITY
DEFINER` que devuelve solo categorías e intereses activos. Es el mecanismo
público: el registro la consume antes de que exista sesión, igual que
`app.alias_exists` para el alias (`docs/api-contracts.md` §16.2).

La selección personal vive en `public.intereses_usuario`, con RLS activa:
cada usuario solo puede insertar y borrar sus propias filas. El filtro de
intereses activos vive en el SQL de la inserción (defensa en profundidad).
"""

from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from Chatly.backend.core.errors import ValidationError
from Chatly.backend.database.session import get_app_session_factory
from Chatly.backend.schemas.interests import InterestCategoryDTO, InterestItemDTO

_INVALID_INTEREST_MESSAGE = (
    "Alguno de los intereses seleccionados no existe o ya no está disponible."
)


class InterestRepository:
    """Acceso al catálogo de intereses y a `intereses_usuario`."""

    async def list_catalog(self) -> list[InterestCategoryDTO]:
        """Categorías activas con sus intereses, en el orden del catálogo."""
        async with get_app_session_factory()() as session:
            result = await session.execute(text("select * from app.catalogo_intereses()"))
            rows = result.all()

        categories: list[InterestCategoryDTO] = []
        by_category: dict[UUID, InterestCategoryDTO] = {}
        for categoria_id, categoria, _orden, interes_id, interes in rows:
            category = by_category.get(categoria_id)
            if category is None:
                category = InterestCategoryDTO(id=categoria_id, name=categoria, interests=[])
                by_category[categoria_id] = category
                categories.append(category)
            category.interests.append(InterestItemDTO(id=interes_id, name=interes))
        return categories

    async def active_interest_ids(self) -> set[UUID]:
        """IDs de todos los intereses activos del catálogo."""
        return {
            interest.id for category in await self.list_catalog() for interest in category.interests
        }

    async def insert_selection(
        self,
        session: AsyncSession,
        user_id: UUID,
        interest_ids: list[UUID],
    ) -> None:
        """Inserta la selección del usuario dentro de la transacción abierta.

        Solo se asocian intereses activos que existen (el filtro `activo` está
        en el SQL). Si no se insertan todos, se lanza `ValidationError` y la
        transacción se revierte completa.
        """
        if not interest_ids:
            return
        result = await session.execute(
            text(
                "insert into public.intereses_usuario (usuario_id, interes_id) "
                "select :usuario_id, i.id from public.intereses i "
                "where i.id = any(cast(:interes_ids as uuid[])) and i.activo "
                "returning interes_id"
            ),
            {
                "usuario_id": str(user_id),
                "interes_ids": [str(interest_id) for interest_id in interest_ids],
            },
        )
        inserted = len(result.all())
        if inserted != len(interest_ids):
            raise ValidationError(_INVALID_INTEREST_MESSAGE)


@lru_cache
def get_interest_repository() -> InterestRepository:
    """Instancia única del repositorio por proceso."""
    return InterestRepository()
