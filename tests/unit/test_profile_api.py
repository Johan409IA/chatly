"""Pruebas de los endpoints de perfil y búsqueda (`backend/api/routes/profile.py`).

Patrón de `tests/unit/test_auth_api.py`: app mínima con los handlers del
repertorio, doble del repositorio de perfiles mediante `dependency_overrides`
y verificador JWT falso. Sin red ni base de datos real.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from Chatly.backend.api import deps
from Chatly.backend.api.routes.profile import router as profile_router
from Chatly.backend.core.errors import (
    ConflictError,
    DomainError,
    ErrorCode,
    domain_error_handler,
    validation_exception_handler,
)
from Chatly.backend.core.jwt import Actor
from Chatly.backend.repositories.profile_repository import (
    _campos_a_actualizar,
    alias_is_changeable,
)
from Chatly.backend.schemas.profile import (
    InterestTagDTO,
    ProfileMeDTO,
    ProfileUpdateRequest,
    UserSearchResultDTO,
)

_ACCESS_TOKEN = "token-de-acceso"
_ACTOR_ID = uuid4()
_ACTOR_EMAIL = "johan@example.com"
_OTRO_ID = uuid4()

_INTERES_PROGRAMACION = UUID("11111111-1111-4111-8111-111111111111")
_INTERES_IA = UUID("22222222-2222-4222-8222-222222222222")
_CATALOGO = {
    _INTERES_PROGRAMACION: ("Programación", "Tecnología"),
    _INTERES_IA: ("Inteligencia artificial", "Tecnología"),
}

_PERFIL_BASE = {
    "alias": "johan_dev",
    "display_name": "Johan Castillón",
    "birth_date": date(2000, 1, 1),
    "gender": "masculino",
    "is_public": True,
    "alias_cambiado_en": None,
    "email_verified": True,
}

_HEADERS = {"Authorization": f"Bearer {_ACCESS_TOKEN}"}


class _StubVerifier:
    """Verificador JWT falso: solo acepta el access token de prueba."""

    def __init__(self) -> None:
        self.tokens: dict[str, Actor] = {}

    def verify(self, token: str) -> Actor:
        actor = self.tokens.get(token)
        if actor is None:
            raise jwt.InvalidTokenError("token de prueba inválido")
        return actor


class _FakeProfileRepository:
    """Doble del repositorio de perfiles: estado en memoria.

    El cooldown de alias se evalúa con la función real
    `alias_is_changeable`, que es la regla compartida entre `can_change_alias`
    y la validación de `update_me`.
    """

    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {str(_ACTOR_ID): dict(_PERFIL_BASE)}
        self.interests: dict[str, list[UUID]] = {str(_ACTOR_ID): []}
        self.aliases_taken: set[str] = set()
        self.verified = True
        self.otros_usuarios: list[dict[str, Any]] = [
            {
                "id": _OTRO_ID,
                "alias": "ana_ml",
                "display_name": "Ana Martínez",
                "email": "ana@example.com",
            },
            {
                "id": uuid4(),
                "alias": "anabel",
                "display_name": "Anabel López",
                "email": "anabel@example.com",
            },
        ]

    async def is_verified(self, user_id: str) -> bool:
        return self.verified and user_id in self.profiles

    async def get_me(self, user_id: str, email: str | None = None) -> ProfileMeDTO | None:
        profile = self.profiles.get(user_id)
        if profile is None:
            return None
        return ProfileMeDTO(
            id=user_id,
            email=email or "",
            email_verified=profile["email_verified"],
            alias=profile["alias"],
            display_name=profile["display_name"],
            birth_date=profile["birth_date"],
            age=26,
            gender=profile["gender"],
            alias_changed_at=profile["alias_cambiado_en"],
            can_change_alias=alias_is_changeable(profile["alias_cambiado_en"]),
            is_public=profile["is_public"],
            interests=[
                InterestTagDTO(id=i, name=_CATALOGO[i][0], category=_CATALOGO[i][1])
                for i in self.interests[user_id]
            ],
            created_at=datetime(2026, 11, 1, tzinfo=UTC),
        )

    async def update_me(self, user_id: str, change: Any) -> None:
        profile = self.profiles[user_id]
        fields = change.model_dump(exclude_unset=True)
        if "alias" in fields and fields["alias"] != profile["alias"]:
            if not alias_is_changeable(profile["alias_cambiado_en"]):
                raise ConflictError(
                    ErrorCode.ALIAS_CHANGE_TOO_SOON,
                    "Solo puedes cambiar tu alias una vez cada 30 días.",
                )
            if fields["alias"] in self.aliases_taken:
                raise ConflictError(ErrorCode.ALIAS_TAKEN, "Ese alias ya está en uso.")
            profile["alias"] = fields["alias"]
            profile["alias_cambiado_en"] = datetime.now(UTC)
        for field, value in fields.items():
            if field != "alias":
                profile[field] = value

    async def replace_interests(self, user_id: str, interest_ids: list[UUID]) -> None:
        self.interests[user_id] = list(interest_ids)

    async def search_users(
        self, actor_id: str, *, q: str | None = None, email: str | None = None
    ) -> list[UserSearchResultDTO]:
        if email is not None:
            coincidencias = [u for u in self.otros_usuarios if u["email"] == email.strip().lower()]
        else:
            coincidencias = [
                u
                for u in self.otros_usuarios
                if str(u["id"]) != actor_id and q.lower() in u["alias"]
            ]
        return [
            UserSearchResultDTO(id=str(u["id"]), alias=u["alias"], display_name=u["display_name"])
            for u in coincidencias[:20]
        ]


@pytest.fixture
def cliente(monkeypatch) -> TestClient:
    """App mínima con el router de perfil y el JWT falso."""
    fake = _FakeProfileRepository()
    stub = _StubVerifier()
    stub.tokens[_ACCESS_TOKEN] = Actor(id=_ACTOR_ID, email=_ACTOR_EMAIL)
    monkeypatch.setattr(deps, "get_jwt_verifier", lambda: stub)

    app = FastAPI()
    app.include_router(profile_router)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.dependency_overrides[deps.get_profile_repository_dep] = lambda: fake

    client = TestClient(app, raise_server_exceptions=False)
    client.fake = fake  # type: ignore[attr-defined]
    yield client
    app.dependency_overrides.clear()


# ------------------------------------------------------------------- GET /api/me


def test_sin_sesion_responde_401(cliente: TestClient) -> None:
    response = cliente.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_get_me_responde_el_perfil_completo(cliente: TestClient) -> None:
    response = cliente.get("/api/me", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(_ACTOR_ID)
    assert body["email"] == _ACTOR_EMAIL
    assert body["email_verified"] is True
    assert body["alias"] == "johan_dev"
    assert body["display_name"] == "Johan Castillón"
    assert body["age"] == 26
    assert body["can_change_alias"] is True
    assert body["is_public"] is True
    assert body["interests"] == []


def test_get_me_sin_perfil_responde_404(cliente: TestClient) -> None:
    cliente.fake.profiles.pop(str(_ACTOR_ID))  # type: ignore[attr-defined]
    response = cliente.get("/api/me", headers=_HEADERS)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ------------------------------------------------------------------ PATCH /api/me


def test_patch_vacio_responde_422(cliente: TestClient) -> None:
    """Sin ningún campo, `PATCH /api/me` se rechaza (§5.2: al menos uno)."""
    response = cliente.patch("/api/me", json={}, headers=_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_patch_is_public_es_independiente(cliente: TestClient) -> None:
    """Cambiar la visibilidad no altera el resto de campos (Q116)."""
    response = cliente.patch("/api/me", json={"is_public": False}, headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["is_public"] is False
    assert body["alias"] == "johan_dev"
    assert body["display_name"] == "Johan Castillón"
    assert body["can_change_alias"] is True

    perfil = cliente.get("/api/me", headers=_HEADERS).json()
    assert perfil["is_public"] is False
    assert perfil["alias"] == "johan_dev"


def test_alias_tomado_responde_409_alias_taken(cliente: TestClient) -> None:
    cliente.fake.aliases_taken.add("ana_ml")  # type: ignore[attr-defined]
    response = cliente.patch("/api/me", json={"alias": "ana_ml"}, headers=_HEADERS)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "alias_taken"


def test_segundo_cambio_de_alias_en_30_dias_responde_409(cliente: TestClient) -> None:
    """El cooldown de 30 días bloquea un nuevo cambio inmediato (Q107)."""
    cliente.fake.profiles[str(_ACTOR_ID)]["alias_cambiado_en"] = datetime.now(  # type: ignore[attr-defined]
        UTC
    ) - timedelta(days=5)

    response = cliente.patch("/api/me", json={"alias": "nuevo_alias"}, headers=_HEADERS)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "alias_change_too_soon"
    assert cliente.fake.profiles[str(_ACTOR_ID)]["alias"] == "johan_dev"  # type: ignore[attr-defined]


def test_alias_despues_del_cooldown_se_acepta(cliente: TestClient) -> None:
    """Pasados 30 días, el alias vuelve a poder cambiarse."""
    cliente.fake.profiles[str(_ACTOR_ID)]["alias_cambiado_en"] = datetime.now(  # type: ignore[attr-defined]
        UTC
    ) - timedelta(days=31)

    response = cliente.patch("/api/me", json={"alias": "nuevo_alias"}, headers=_HEADERS)

    assert response.status_code == 200
    assert response.json()["alias"] == "nuevo_alias"


def test_patch_con_alias_actual_no_dispara_el_cooldown(cliente: TestClient) -> None:
    """Reenviar el alias vigente no cuenta como cambio."""
    cliente.fake.profiles[str(_ACTOR_ID)]["alias_cambiado_en"] = datetime.now(  # type: ignore[attr-defined]
        UTC
    ) - timedelta(days=5)

    response = cliente.patch("/api/me", json={"alias": "johan_dev"}, headers=_HEADERS)

    assert response.status_code == 200
    assert response.json()["alias"] == "johan_dev"


def test_patch_con_campo_invalido_responde_422(cliente: TestClient) -> None:
    response = cliente.patch("/api/me", json={"display_name": "a"}, headers=_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --------------------------------------------------------- PUT /api/me/interests


def test_once_intereses_responde_422(cliente: TestClient) -> None:
    """Más de 10 intereses devuelve `interest_limit_exceeded` (Q124)."""
    interest_ids = [str(uuid4()) for _ in range(11)]
    response = cliente.put(
        "/api/me/interests", json={"interest_ids": interest_ids}, headers=_HEADERS
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "interest_limit_exceeded"
    assert cliente.fake.interests[str(_ACTOR_ID)] == []  # type: ignore[attr-defined]


def test_reemplazo_de_intereses_persiste(cliente: TestClient) -> None:
    interest_ids = [str(_INTERES_PROGRAMACION), str(_INTERES_IA)]
    response = cliente.put(
        "/api/me/interests", json={"interest_ids": interest_ids}, headers=_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert [i["id"] for i in body["interests"]] == interest_ids
    assert body["interests"][0]["category"] == "Tecnología"


def test_reemplazo_con_lista_vacia_se_acepta(cliente: TestClient) -> None:
    """La lista vacía equivale a omitir la selección (Q117)."""
    cliente.fake.interests[str(_ACTOR_ID)] = [_INTERES_PROGRAMACION]  # type: ignore[attr-defined]
    response = cliente.put("/api/me/interests", json={"interest_ids": []}, headers=_HEADERS)

    assert response.status_code == 200
    assert response.json()["interests"] == []


def test_reemplazo_con_intereses_duplicados_responde_422(cliente: TestClient) -> None:
    response = cliente.put(
        "/api/me/interests",
        json={"interest_ids": [str(_INTERES_IA), str(_INTERES_IA)]},
        headers=_HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ----------------------------------------------------------- GET /api/users/search


def test_busqueda_por_alias_excluye_al_propio_usuario_y_no_devuelve_correo(
    cliente: TestClient,
) -> None:
    response = cliente.get("/api/users/search", params={"q": "ana"}, headers=_HEADERS)

    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["alias"] for r in results] == ["ana_ml", "anabel"]
    assert all("email" not in r for r in results)
    assert all(r["id"] != str(_ACTOR_ID) for r in results)


def test_busqueda_por_correo_exacto(cliente: TestClient) -> None:
    response = cliente.get(
        "/api/users/search", params={"email": "ana@example.com"}, headers=_HEADERS
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["alias"] == "ana_ml"
    assert "email" not in results[0]


def test_busqueda_sin_parametros_responde_422(cliente: TestClient) -> None:
    response = cliente.get("/api/users/search", headers=_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_busqueda_con_ambos_parametros_responde_422(cliente: TestClient) -> None:
    response = cliente.get(
        "/api/users/search", params={"q": "ana", "email": "ana@example.com"}, headers=_HEADERS
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_busqueda_con_q_muy_corta_responde_422(cliente: TestClient) -> None:
    """Menos de 2 caracteres no es búsqueda parcial válida (Q112)."""
    response = cliente.get("/api/users/search", params={"q": "a"}, headers=_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_busqueda_sin_correo_confirmado_responde_403(cliente: TestClient) -> None:
    """La búsqueda exige usuario verificado (Q112), a diferencia de `/api/me`."""
    cliente.fake.verified = False  # type: ignore[attr-defined]
    response = cliente.get("/api/users/search", params={"q": "ana"}, headers=_HEADERS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


# --------------------------------------------------------------- regla del alias


def test_alias_es_cambiable_sin_cambios_previos() -> None:
    assert alias_is_changeable(None) is True


def test_alias_no_es_cambiable_dentro_del_cooldown() -> None:
    cambiado = datetime.now(UTC) - timedelta(days=29, hours=23)
    assert alias_is_changeable(cambiado) is False


def test_alias_es_cambiable_pasado_el_cooldown() -> None:
    cambiado = datetime.now(UTC) - timedelta(days=30)
    assert alias_is_changeable(cambiado) is True


# --------------------------------------------------------- campos a actualizar


def test_campo_enviado_como_null_equivale_a_no_enviarlo() -> None:
    """Un `null` explícito no alcanza el UPDATE (rompería el `NOT NULL`)."""
    change = ProfileUpdateRequest.model_validate({"display_name": "Johan", "is_public": None})

    assert _campos_a_actualizar(change) == {"nombre_visible": "Johan"}


def test_los_campos_se_mapean_a_columnas() -> None:
    change = ProfileUpdateRequest.model_validate(
        {
            "alias": "nuevo_alias",
            "display_name": "Nombre Nuevo",
            "birth_date": date(1999, 5, 10),
            "gender": "femenino",
            "is_public": False,
        }
    )

    assert _campos_a_actualizar(change) == {
        "alias": "nuevo_alias",
        "nombre_visible": "Nombre Nuevo",
        "fecha_nacimiento": date(1999, 5, 10),
        "genero": "femenino",
        "visibilidad_publica": False,
    }


def test_solo_nulos_lo_rechaza_el_esquema() -> None:
    """El esquema no deja llegar al repositorio un PATCH sin campos reales."""
    with pytest.raises(DomainError) as excinfo:
        ProfileUpdateRequest.model_validate({"is_public": None})

    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
