"""Endpoints del perfil propio y de búsqueda de usuarios
(`docs/api-contracts.md` §5, §6.1 y §16.2).

`/api/me` y `/api/me/interests` usan `require_actor` (no `VerifiedActor`):
un usuario sin confirmar el correo debe poder completar su perfil. La
búsqueda de usuarios sí exige `VerifiedActor` (Q112). La identidad siempre
sale del JWT; el correo de `ProfileMe` viaja en el token, porque
`contactos_usuario` no tiene grant de lectura para `chatly_app`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from Chatly.backend.api.deps import ProfileRepositoryDep, VerifiedActor, require_actor
from Chatly.backend.core.errors import DomainError, ErrorCode, NotFoundError
from Chatly.backend.core.jwt import Actor
from Chatly.backend.schemas.profile import (
    InterestsUpdateRequest,
    ProfileMeDTO,
    ProfileUpdateRequest,
    UserSearchResponse,
)

router = APIRouter(tags=["profile"])

ActorDep = Annotated[Actor, Depends(require_actor)]

_MIN_QUERY_LENGTH = 2


async def _require_profile(repository: ProfileRepositoryDep, actor: Actor) -> ProfileMeDTO:
    """Perfil propio o `404 not_found` si aún no existe."""
    profile = await repository.get_me(str(actor.id), email=actor.email)
    if profile is None:
        raise NotFoundError()
    return profile


@router.get("/api/me", response_model=ProfileMeDTO)
async def get_me(actor: ActorDep, repository: ProfileRepositoryDep) -> ProfileMeDTO:
    """Perfil propio completo (§5.1)."""
    return await _require_profile(repository, actor)


@router.patch("/api/me", response_model=ProfileMeDTO)
async def update_me(
    actor: ActorDep, change: ProfileUpdateRequest, repository: ProfileRepositoryDep
) -> ProfileMeDTO:
    """Actualiza los campos enviados y responde con el perfil vigente (§5.2)."""
    await repository.update_me(str(actor.id), change)
    return await _require_profile(repository, actor)


@router.put("/api/me/interests", response_model=ProfileMeDTO)
async def replace_interests(
    actor: ActorDep, body: InterestsUpdateRequest, repository: ProfileRepositoryDep
) -> ProfileMeDTO:
    """Reemplaza la selección completa de intereses (§16.2)."""
    await repository.replace_interests(str(actor.id), body.interest_ids)
    return await _require_profile(repository, actor)


@router.get("/api/users/search", response_model=UserSearchResponse)
async def search_users(
    actor: VerifiedActor,
    repository: ProfileRepositoryDep,
    q: str | None = None,
    email: str | None = None,
) -> UserSearchResponse:
    """Búsqueda parcial por alias o exacta por correo, mutuamente excluyentes (§6.1)."""
    if (q is None) == (email is None):
        raise DomainError(
            ErrorCode.VALIDATION_ERROR,
            "Indica un parámetro de búsqueda: `q` o `email`, pero no ambos.",
            status_code=422,
        )
    if q is not None:
        q = q.strip()
        if len(q) < _MIN_QUERY_LENGTH:
            raise DomainError(
                ErrorCode.VALIDATION_ERROR,
                "La búsqueda por alias necesita al menos 2 caracteres.",
                status_code=422,
            )
    results = await repository.search_users(str(actor.id), q=q, email=email)
    return UserSearchResponse(results=results)
