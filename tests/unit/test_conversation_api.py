"""Pruebas de los endpoints de conversaciones y grupos (§7.2–7.9).

Patrón de `tests/unit/test_profile_api.py`: app mínima con los handlers del
repertorio, doble del repositorio de conversaciones mediante
`dependency_overrides` y verificador JWT falso. Sin red ni base de datos.

Las reglas puras del repositorio (tamaño de grupo, chat con uno mismo) se
prueban contra la clase real: se validan ANTES de abrir la transacción, así
que no tocan la base de datos.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from Chatly.backend.api import deps
from Chatly.backend.api.routes.chat import router as chat_router
from Chatly.backend.core.errors import (
    ConflictError,
    DomainError,
    ErrorCode,
    ForbiddenError,
    ValidationError,
    domain_error_handler,
    validation_exception_handler,
)
from Chatly.backend.core.jwt import Actor
from Chatly.backend.repositories.conversation_repository import ConversationRepository
from Chatly.backend.schemas.chat import (
    ConversationDetail,
    ConversationList,
    ConversationSummary,
    DirectConversationResponse,
    LeaveResponse,
    MemberItem,
    MembershipCreated,
    MyMembership,
    UserSummary,
)

_ACCESS_TOKEN = "token-de-acceso"
_TOKEN_AJENO = "token-de-otro"
_ACTOR_ID = uuid4()
_ACTOR_EMAIL = "johan@example.com"
_OTRO_ID = uuid4()
_TERCERO_ID = uuid4()
_CONVERSACION_ID = uuid4()

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


def _resumen() -> ConversationSummary:
    return ConversationSummary(
        id=_CONVERSACION_ID,
        type="group",
        name="Equipo de tesis",
        initials="ET",
        last_message_at=None,
        last_message_preview=None,
        unread_count=2,
        is_archived=False,
        my_role="admin",
        members_count=3,
        is_discoverable=False,
        description=None,
    )


def _detalle() -> ConversationDetail:
    return ConversationDetail(
        id=_CONVERSACION_ID,
        type="group",
        name="Equipo de tesis",
        admin_id=_ACTOR_ID,
        is_archived=False,
        is_discoverable=False,
        description=None,
        created_at=datetime(2026, 11, 20, tzinfo=UTC),
        members=[
            MemberItem(
                user=UserSummary(id=_ACTOR_ID, alias="johan_dev", display_name="Johan Castillón"),
                role="admin",
                joined_at=datetime(2026, 11, 20, tzinfo=UTC),
                left_at=None,
                active=True,
            )
        ],
        my_membership=MyMembership(
            role="admin", active=True, joined_at=datetime(2026, 11, 20, tzinfo=UTC)
        ),
    )


class _FakeConversationRepository:
    """Doble del repositorio de conversaciones: respuestas en memoria."""

    def __init__(self) -> None:
        self.verified = True
        self.direct_response = DirectConversationResponse(
            conversation_id=None,
            is_temporary=True,
            conversation=None,
            recipient=UserSummary(id=_OTRO_ID, alias="ana_ml", display_name="Ana Martínez"),
        )

    async def list_conversations(
        self, actor_id: str, *, include_hidden: bool = False
    ) -> ConversationList:
        return ConversationList(items=[_resumen()], total_unread=2)

    async def get_or_preview_direct(
        self, actor_id: str, recipient_id: str
    ) -> DirectConversationResponse:
        return self.direct_response

    async def create_group(
        self, actor_id: str, name: str, member_ids: list[str]
    ) -> ConversationDetail:
        return _detalle()

    async def get_conversation(self, actor_id: str, conversation_id: str) -> ConversationDetail:
        return _detalle()

    async def rename_group(
        self, actor_id: str, conversation_id: str, name: str
    ) -> ConversationDetail:
        if actor_id != str(_ACTOR_ID):
            raise ForbiddenError("Solo el administrador puede hacer esto.")
        return _detalle()

    async def add_member(
        self, actor_id: str, conversation_id: str, user_id: str
    ) -> MembershipCreated:
        if user_id == str(_OTRO_ID):
            raise ConflictError(ErrorCode.ALREADY_MEMBER, "Ya es integrante del grupo.")
        return MembershipCreated(
            conversation_id=UUID(conversation_id),
            user_id=UUID(user_id),
            role="member",
            joined_at=datetime(2026, 11, 26, tzinfo=UTC),
        )

    async def remove_member(self, actor_id: str, conversation_id: str, user_id: str) -> None:
        if actor_id != str(_ACTOR_ID):
            raise ForbiddenError("Solo el administrador puede hacer esto.")
        return None

    async def leave(self, actor_id: str, conversation_id: str, mode: str) -> LeaveResponse:
        return LeaveResponse(archived=True, new_admin_id=None)

    async def set_hidden(self, actor_id: str, conversation_id: str, hidden: bool) -> None:
        return None


class _FakeVerifiedProfiles:
    """Doble mínimo del repositorio de perfiles para `VerifiedActor`."""

    def __init__(self) -> None:
        self.verified = True

    async def is_verified(self, user_id: str) -> bool:
        return self.verified


@pytest.fixture
def cliente(monkeypatch) -> TestClient:
    """App mínima con el router de chat y el JWT falso."""
    fake = _FakeConversationRepository()
    profiles = _FakeVerifiedProfiles()
    stub = _StubVerifier()
    stub.tokens[_ACCESS_TOKEN] = Actor(id=_ACTOR_ID, email=_ACTOR_EMAIL)
    monkeypatch.setattr(deps, "get_jwt_verifier", lambda: stub)

    app = FastAPI()
    app.include_router(chat_router)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.dependency_overrides[deps.get_conversation_repository_dep] = lambda: fake
    app.dependency_overrides[deps.get_profile_repository_dep] = lambda: profiles

    client = TestClient(app, raise_server_exceptions=False)
    client.fake = fake  # type: ignore[attr-defined]
    client.profiles = profiles  # type: ignore[attr-defined]
    client.stub = stub  # type: ignore[attr-defined]
    yield client
    app.dependency_overrides.clear()


# ------------------------------------------------------------- autorización


def test_sin_sesion_responde_401(cliente: TestClient) -> None:
    response = cliente.get("/api/conversations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_sin_correo_confirmado_responde_403(cliente: TestClient) -> None:
    """Todo el chat exige usuario verificado (criterio de la Iteración 2)."""
    cliente.profiles.verified = False  # type: ignore[attr-defined]
    response = cliente.get("/api/conversations", headers=_HEADERS)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


# --------------------------------------------------------- GET /api/conversations


def test_listado_devuelve_items_y_total_no_leidos(cliente: TestClient) -> None:
    response = cliente.get("/api/conversations", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total_unread"] == 2
    assert body["items"][0]["name"] == "Equipo de tesis"
    assert body["items"][0]["is_discoverable"] is False


# ------------------------------------------------- POST /api/conversations/direct


def test_directo_temporal_devuelve_destinatario_sin_conversacion(
    cliente: TestClient,
) -> None:
    response = cliente.post(
        "/api/conversations/direct", json={"recipient_id": str(_OTRO_ID)}, headers=_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] is None
    assert body["is_temporary"] is True
    assert body["recipient"]["alias"] == "ana_ml"


def test_directo_existente_reutiliza_la_conversacion(cliente: TestClient) -> None:
    existente = DirectConversationResponse(
        conversation_id=_CONVERSACION_ID,
        is_temporary=False,
        conversation=_resumen(),
        recipient=UserSummary(id=_OTRO_ID, alias="ana_ml", display_name="Ana Martínez"),
    )
    cliente.fake.direct_response = existente  # type: ignore[attr-defined]
    response = cliente.post(
        "/api/conversations/direct", json={"recipient_id": str(_OTRO_ID)}, headers=_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_temporary"] is False
    assert body["conversation_id"] == str(_CONVERSACION_ID)


# -------------------------------------------------- POST /api/conversations/groups


def test_crear_grupo_responde_201_con_detalle(cliente: TestClient) -> None:
    response = cliente.post(
        "/api/conversations/groups",
        json={"name": "Equipo de tesis", "member_ids": [str(_OTRO_ID), str(_TERCERO_ID)]},
        headers=_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "group"
    assert body["admin_id"] == str(_ACTOR_ID)
    assert body["members"][0]["role"] == "admin"


def test_nombre_de_grupo_muy_corto_responde_422(cliente: TestClient) -> None:
    """El nombre se valida en el esquema: 3–40 caracteres (Q87)."""
    response = cliente.post(
        "/api/conversations/groups",
        json={"name": "ab", "member_ids": [str(_OTRO_ID), str(_TERCERO_ID)]},
        headers=_HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ----------------------------------------------- reglas puras del repositorio


async def test_grupo_con_un_solo_invitado_responde_422() -> None:
    """Mínimo 3 integrantes contando al creador (Q89); no toca la base."""
    repo = ConversationRepository()
    with pytest.raises(ValidationError):
        await repo.create_group(str(_ACTOR_ID), "Equipo", [str(_OTRO_ID)])


async def test_grupo_con_mas_de_diez_responde_409() -> None:
    """Máximo 10 integrantes incluyendo al creador (Q8)."""
    repo = ConversationRepository()
    otros = [str(uuid4()) for _ in range(10)]
    with pytest.raises(ConflictError) as excinfo:
        await repo.create_group(str(_ACTOR_ID), "Equipo", otros)

    assert excinfo.value.code == ErrorCode.CONVERSATION_FULL


async def test_creador_duplicado_en_la_lista_no_cuenta_dos_veces() -> None:
    """Si el creador aparece en `member_ids`, no se cuenta dos veces."""
    repo = ConversationRepository()
    with pytest.raises(ValidationError):
        # Creador + 1 invitado repetido = 2 integrantes efectivos: menos de 3.
        await repo.create_group(
            str(_ACTOR_ID), "Equipo", [str(_ACTOR_ID), str(_OTRO_ID), str(_OTRO_ID)]
        )


async def test_chat_directo_con_uno_mismo_responde_422() -> None:
    repo = ConversationRepository()
    with pytest.raises(ValidationError):
        await repo.get_or_preview_direct(str(_ACTOR_ID), str(_ACTOR_ID))


# ------------------------------------------------------------- membresías


def test_anadir_miembro_ya_integrante_responde_409(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/members",
        json={"user_id": str(_OTRO_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_member"


def test_anadir_miembro_responde_201(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/members",
        json={"user_id": str(_TERCERO_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(_TERCERO_ID)


def test_expulsion_por_no_admin_responde_403(cliente: TestClient) -> None:
    """Solo el administrador activo expulsa (Q35)."""
    cliente.stub.tokens[_TOKEN_AJENO] = Actor(  # type: ignore[attr-defined]
        id=_OTRO_ID, email="ana@example.com"
    )

    response = cliente.delete(
        f"/api/conversations/{_CONVERSACION_ID}/members/{_TERCERO_ID}",
        headers={"Authorization": f"Bearer {_TOKEN_AJENO}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_expulsion_responde_204(cliente: TestClient) -> None:
    response = cliente.delete(
        f"/api/conversations/{_CONVERSACION_ID}/members/{_OTRO_ID}",
        headers=_HEADERS,
    )

    assert response.status_code == 204


def test_salir_del_ultimo_responde_archivada(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/leave",
        json={"mode": "keep_history"},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["archived"] is True
    assert body["new_admin_id"] is None


def test_preferencia_oculta_responde_200(cliente: TestClient) -> None:
    response = cliente.put(
        f"/api/conversations/{_CONVERSACION_ID}/preferences",
        json={"hidden": True},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"hidden": True}


def test_detalle_devuelve_miembros_y_membresia_propia(cliente: TestClient) -> None:
    response = cliente.get(f"/api/conversations/{_CONVERSACION_ID}", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["my_membership"]["role"] == "admin"
    assert body["members"][0]["user"]["alias"] == "johan_dev"
