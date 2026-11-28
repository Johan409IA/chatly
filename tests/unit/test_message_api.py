"""Pruebas de los endpoints de mensajes (§7.2.1 y §8).

Patrón de `tests/unit/test_conversation_api.py`: app mínima con los handlers
del repertorio, doble de `MessageRepository` mediante `dependency_overrides`
y verificador JWT falso. Sin red ni base de datos.

Las reglas puras del repositorio (longitud del contenido, chat con uno
mismo, cursor incompleto) se prueban contra la clase real: se validan ANTES
de abrir la transacción, así que no tocan la base de datos.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from Chatly.backend.api import deps
from Chatly.backend.api.routes.chat import router as chat_router
from Chatly.backend.core.errors import (
    DomainError,
    ErrorCode,
    ForbiddenError,
    ValidationError,
    domain_error_handler,
    validation_exception_handler,
)
from Chatly.backend.core.jwt import Actor
from Chatly.backend.repositories.message_repository import MessageRepository, SendResult
from Chatly.backend.schemas.chat import (
    Message,
    MessageAuthor,
    MessageCursor,
    MessageList,
    ReadResponse,
    ReadStatus,
    ReplyPreview,
)

_ACCESS_TOKEN = "token-de-acceso"
_ACTOR_ID = uuid4()
_OTRO_ID = uuid4()
_CONVERSACION_ID = uuid4()
_MENSAJE_ID = uuid4()
_RESPUESTA_ID = uuid4()

_HEADERS = {"Authorization": f"Bearer {_ACCESS_TOKEN}"}
_BASE_TIME = datetime(2026, 12, 24, 18, 0, 0, tzinfo=UTC)


class _StubVerifier:
    """Verificador JWT falso: solo acepta el access token de prueba."""

    def __init__(self) -> None:
        self.tokens: dict[str, Actor] = {}

    def verify(self, token: str) -> Actor:
        actor = self.tokens.get(token)
        if actor is None:
            raise jwt.InvalidTokenError("token de prueba inválido")
        return actor


def _mensaje(*, reply_to: ReplyPreview | None = None, read: ReadStatus | None = None) -> Message:
    return Message(
        id=_MENSAJE_ID,
        conversation_id=_CONVERSACION_ID,
        type="text",
        author=MessageAuthor(id=_ACTOR_ID, alias="johan_dev", display_name="Johan Castillón"),
        content="Hola a todos",
        edited_at=None,
        deleted=False,
        reply_to=reply_to,
        read=read,
        created_at=_BASE_TIME,
    )


class _FakeMessageRepository:
    """Doble del repositorio de mensajes: respuestas en memoria."""

    def __init__(self) -> None:
        self.replay = False
        self.created = False
        self.last_list_kwargs: dict = {}
        self.error: DomainError | None = None
        self.last_read_message_id: UUID | None = None
        self.last_typing: tuple[str, str, bool] | None = None
        self.typing_names: list[str] = []

    async def list_messages(
        self,
        actor_id: str,
        conversation_id: str,
        *,
        before_created_at=None,
        before_id=None,
        limit=None,
    ) -> MessageList:
        if (before_created_at is None) != (before_id is None):
            raise ValidationError("El cursor necesita `before_created_at` y `before_id` juntos.")
        self.last_list_kwargs = {
            "before_created_at": before_created_at,
            "before_id": before_id,
            "limit": limit,
        }
        cursor = MessageCursor(created_at=_BASE_TIME, id=_MENSAJE_ID)
        if before_created_at is not None:
            return MessageList(items=[], next_cursor=None)
        return MessageList(items=[_mensaje()], next_cursor=cursor)

    async def send_message(
        self,
        actor_id: str,
        conversation_id: str,
        content: str,
        client_message_id: UUID,
        reply_to_message_id: UUID | None = None,
    ) -> SendResult:
        if self.error is not None:
            raise self.error
        mensaje = _mensaje(
            reply_to=(
                ReplyPreview(id=reply_to_message_id, author_alias="ana_ml", preview="Hola")
                if reply_to_message_id
                else None
            )
        )
        return SendResult(
            message=mensaje,
            idempotent_replay=self.replay,
            conversation_id=UUID(conversation_id),
        )

    async def send_direct_message(
        self, actor_id: str, recipient_id: str, content: str, client_message_id: UUID
    ) -> SendResult:
        if self.error is not None:
            raise self.error
        return SendResult(
            message=_mensaje(),
            idempotent_replay=self.replay,
            conversation_id=_CONVERSACION_ID,
            conversation_created=self.created,
        )

    async def mark_read(
        self, actor_id: str, conversation_id: str, message_id: UUID
    ) -> ReadResponse:
        if self.error is not None:
            raise self.error
        self.last_read_message_id = message_id
        return ReadResponse(last_read_message_id=message_id, last_read_at=_BASE_TIME)

    async def record_typing(
        self, actor_id: str, conversation_id: str, *, is_typing: bool
    ) -> None:
        if self.error is not None:
            raise self.error
        self.last_typing = (conversation_id, actor_id, is_typing)

    async def list_typing(self, actor_id: str, conversation_id: str) -> list[str]:
        if self.error is not None:
            raise self.error
        return list(self.typing_names)


class _FakeVerifiedProfiles:
    """Doble mínimo del repositorio de perfiles para `VerifiedActor`."""

    def __init__(self) -> None:
        self.verified = True

    async def is_verified(self, user_id: str) -> bool:
        return self.verified


@pytest.fixture
def cliente(monkeypatch) -> TestClient:
    """App mínima con el router de chat y el JWT falso."""
    fake = _FakeMessageRepository()
    profiles = _FakeVerifiedProfiles()
    stub = _StubVerifier()
    stub.tokens[_ACCESS_TOKEN] = Actor(id=_ACTOR_ID, email="johan@example.com")
    monkeypatch.setattr(deps, "get_jwt_verifier", lambda: stub)

    app = FastAPI()
    app.include_router(chat_router)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.dependency_overrides[deps.get_message_repository_dep] = lambda: fake
    app.dependency_overrides[deps.get_profile_repository_dep] = lambda: profiles

    client = TestClient(app, raise_server_exceptions=False)
    client.fake = fake  # type: ignore[attr-defined]
    yield client
    app.dependency_overrides.clear()


# ------------------------------------------------------- GET .../messages


def test_historial_devuelve_items_y_cursor(cliente: TestClient) -> None:
    response = cliente.get(f"/api/conversations/{_CONVERSACION_ID}/messages", headers=_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["content"] == "Hola a todos"
    assert body["items"][0]["author"]["alias"] == "johan_dev"
    assert body["next_cursor"]["id"] == str(_MENSAJE_ID)


def test_historial_pasa_el_cursor_al_repositorio(cliente: TestClient) -> None:
    antes = _BASE_TIME.isoformat()
    response = cliente.get(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        params={"before_created_at": antes, "before_id": str(_MENSAJE_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    kwargs = cliente.fake.last_list_kwargs  # type: ignore[attr-defined]
    assert kwargs["before_created_at"] == _BASE_TIME
    assert kwargs["before_id"] == _MENSAJE_ID
    assert kwargs["limit"] is None  # sin límite explícito: el repo decide 50/30 (Q94)


def test_historial_sin_limite_inicial_es_50(cliente: TestClient) -> None:
    cliente.get(f"/api/conversations/{_CONVERSACION_ID}/messages", headers=_HEADERS)

    kwargs = cliente.fake.last_list_kwargs  # type: ignore[attr-defined]
    assert kwargs["limit"] is None  # el repositorio decide: 50 sin cursor


def test_cursor_incompleto_responde_422(cliente: TestClient) -> None:
    response = cliente.get(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        params={"before_id": str(_MENSAJE_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_limite_mayor_a_50_responde_422(cliente: TestClient) -> None:
    response = cliente.get(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        params={"limit": 51},
        headers=_HEADERS,
    )

    assert response.status_code == 422


# ------------------------------------------------------ POST .../messages


def test_envio_responde_201_con_mensaje_y_autoria(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={"content": "Hola a todos", "client_message_id": str(uuid4())},
        headers=_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["idempotent_replay"] is False
    assert body["message"]["author"]["id"] == str(_ACTOR_ID)


def test_reintento_idempotente_responde_200(cliente: TestClient) -> None:
    """El mismo `client_message_id` devuelve el mensaje existente (Q40)."""
    cliente.fake.replay = True  # type: ignore[attr-defined]
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={"content": "Hola a todos", "client_message_id": str(uuid4())},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["idempotent_replay"] is True


def test_envio_sin_sesion_responde_401(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={"content": "Hola", "client_message_id": str(uuid4())},
    )

    assert response.status_code == 401


def test_envio_sin_membresia_responde_403(cliente: TestClient) -> None:
    cliente.fake.error = ForbiddenError("No perteneces a esta conversación.")  # type: ignore[attr-defined]
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={"content": "Hola", "client_message_id": str(uuid4())},
        headers=_HEADERS,
    )

    assert response.status_code == 403


def test_respuesta_valida_conserva_la_referencia(cliente: TestClient) -> None:
    respuesta_id = str(_RESPUESTA_ID)
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={
            "content": "¡De acuerdo!",
            "client_message_id": str(uuid4()),
            "reply_to_message_id": respuesta_id,
        },
        headers=_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["message"]["reply_to"]["id"] == respuesta_id
    assert body["message"]["reply_to"]["author_alias"] == "ana_ml"


def test_respuesta_a_otra_conversacion_responde_422(cliente: TestClient) -> None:
    cliente.fake.error = ValidationError(  # type: ignore[attr-defined]
        "El mensaje al que respondes no pertenece a esta conversación."
    )
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={
            "content": "¡De acuerdo!",
            "client_message_id": str(uuid4()),
            "reply_to_message_id": str(_RESPUESTA_ID),
        },
        headers=_HEADERS,
    )

    assert response.status_code == 422


def test_envio_sin_client_message_id_lo_genera_el_servidor(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/messages",
        json={"content": "Hola"},
        headers=_HEADERS,
    )

    assert response.status_code == 201


# ------------------------------------------------- POST /api/messages/direct


def test_directo_nuevo_responde_201(cliente: TestClient) -> None:
    cliente.fake.created = True  # type: ignore[attr-defined]
    response = cliente.post(
        "/api/messages/direct",
        json={
            "recipient_id": str(_OTRO_ID),
            "content": "Hola, comparto tu interés",
            "client_message_id": str(uuid4()),
        },
        headers=_HEADERS,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["conversation_id"] == str(_CONVERSACION_ID)
    assert body["idempotent_replay"] is False


def test_directo_existente_responde_200(cliente: TestClient) -> None:
    response = cliente.post(
        "/api/messages/direct",
        json={
            "recipient_id": str(_OTRO_ID),
            "content": "Hola otra vez",
            "client_message_id": str(uuid4()),
        },
        headers=_HEADERS,
    )

    assert response.status_code == 200


# --------------------------------------------- reglas puras del repositorio


async def test_contenido_de_cuatro_mil_uno_responde_message_too_long() -> None:
    """Más de 4.000 caracteres → `message_too_long` (Q51); no toca la base."""
    repo = MessageRepository()
    with pytest.raises(DomainError) as excinfo:
        await repo.send_message(str(_ACTOR_ID), str(_CONVERSACION_ID), "a" * 4001, uuid4())

    assert excinfo.value.code == ErrorCode.MESSAGE_TOO_LONG


async def test_contenido_solo_espacios_responde_422() -> None:
    repo = MessageRepository()
    with pytest.raises(ValidationError):
        await repo.send_message(str(_ACTOR_ID), str(_CONVERSACION_ID), "   \n  ", uuid4())


async def test_limite_mayor_a_50_en_el_repositorio_responde_422() -> None:
    repo = MessageRepository()
    with pytest.raises(ValidationError):
        await repo.list_messages(str(_ACTOR_ID), str(_CONVERSACION_ID), limit=100)


async def test_cursor_con_un_solo_parametro_responde_422() -> None:
    repo = MessageRepository()
    with pytest.raises(ValidationError):
        await repo.list_messages(str(_ACTOR_ID), str(_CONVERSACION_ID), before_id=_MENSAJE_ID)


async def test_cursor_sin_zona_horaria_responde_422() -> None:
    """El cursor compara `timestamptz`: la marca debe venir con zona."""
    repo = MessageRepository()
    with pytest.raises(ValidationError):
        await repo.list_messages(
            str(_ACTOR_ID),
            str(_CONVERSACION_ID),
            before_created_at=datetime(2026, 12, 24, 18, 0, 0),
            before_id=_MENSAJE_ID,
        )


async def test_chat_directo_con_uno_mismo_responde_422() -> None:
    repo = MessageRepository()
    with pytest.raises(ValidationError):
        await repo.send_direct_message(str(_ACTOR_ID), str(_ACTOR_ID), "Hola", uuid4())


def test_mensaje_eliminado_no_expone_contenido(cliente: TestClient) -> None:
    """Q85: el contenido de un mensaje eliminado no llega en el DTO."""
    eliminado = Message(
        id=uuid4(),
        conversation_id=_CONVERSACION_ID,
        type="text",
        author=MessageAuthor(id=_ACTOR_ID, alias="johan_dev", display_name="Johan"),
        content=None,
        deleted=True,
        created_at=_BASE_TIME + timedelta(minutes=1),
    )
    cliente.fake.replay = False  # type: ignore[attr-defined]
    original = cliente.fake.list_messages  # type: ignore[attr-defined]

    async def con_eliminado(*args, **kwargs):
        return MessageList(items=[_mensaje(), eliminado], next_cursor=None)

    cliente.fake.list_messages = con_eliminado  # type: ignore[attr-defined]
    try:
        response = cliente.get(f"/api/conversations/{_CONVERSACION_ID}/messages", headers=_HEADERS)
    finally:
        cliente.fake.list_messages = original  # type: ignore[attr-defined]

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[-1]["deleted"] is True
    assert items[-1]["content"] is None


# ------------------------------------------------------- POST .../read (§7.10)


def test_marcar_leido_responde_200_con_la_marca(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/read",
        json={"message_id": str(_MENSAJE_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["last_read_message_id"] == str(_MENSAJE_ID)
    assert body["last_read_at"]
    assert cliente.fake.last_read_message_id == _MENSAJE_ID  # type: ignore[attr-defined]


def test_marcar_leido_sin_sesion_responde_401(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/read",
        json={"message_id": str(_MENSAJE_ID)},
    )

    assert response.status_code == 401


def test_marcar_leido_con_error_del_repo_propaga_el_codigo(cliente: TestClient) -> None:
    cliente.fake.error = ValidationError(  # type: ignore[attr-defined]
        "Ese mensaje no pertenece a esta conversación."
    )
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/read",
        json={"message_id": str(_MENSAJE_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 422


def test_marcar_leido_con_membresia_cerrada_responde_403(cliente: TestClient) -> None:
    cliente.fake.error = ForbiddenError("Ya no perteneces a esta conversación.")  # type: ignore[attr-defined]
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/read",
        json={"message_id": str(_MENSAJE_ID)},
        headers=_HEADERS,
    )

    assert response.status_code == 403


def test_historial_incluye_el_estado_de_lectura(cliente: TestClient) -> None:
    """El DTO `read` (§3.4) llega tal cual para pintar ✓ o ✓✓."""
    original = cliente.fake.list_messages  # type: ignore[attr-defined]

    async def con_lectura(*args, **kwargs):
        return MessageList(
            items=[
                _mensaje(
                    read=ReadStatus(all_read=True, read_count=1, expected_count=1),
                )
            ],
            next_cursor=None,
        )

    cliente.fake.list_messages = con_lectura  # type: ignore[attr-defined]
    try:
        response = cliente.get(f"/api/conversations/{_CONVERSACION_ID}/messages", headers=_HEADERS)
    finally:
        cliente.fake.list_messages = original  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert response.json()["items"][0]["read"] == {
        "all_read": True,
        "read_count": 1,
        "expected_count": 1,
    }


# ------------------------------------------- typing efímero (puente REST)


def test_signal_de_escritura_responde_200(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/typing",
        json={"is_typing": True},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    typing = cliente.fake.last_typing  # type: ignore[attr-defined]
    assert typing == (str(_CONVERSACION_ID), str(_ACTOR_ID), True)


def test_fin_de_escritura_llega_con_is_typing_false(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/typing",
        json={"is_typing": False},
        headers=_HEADERS,
    )

    assert response.status_code == 200
    typing = cliente.fake.last_typing  # type: ignore[attr-defined]
    assert typing == (str(_CONVERSACION_ID), str(_ACTOR_ID), False)


def test_signal_de_escritura_sin_sesion_responde_401(cliente: TestClient) -> None:
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/typing",
        json={"is_typing": True},
    )

    assert response.status_code == 401


def test_signal_de_escritura_sin_membresia_responde_403(cliente: TestClient) -> None:
    cliente.fake.error = ForbiddenError("No perteneces a esta conversación.")  # type: ignore[attr-defined]
    response = cliente.post(
        f"/api/conversations/{_CONVERSACION_ID}/typing",
        json={"is_typing": True},
        headers=_HEADERS,
    )

    assert response.status_code == 403


def test_consulta_de_escritura_devuelve_los_nombres(cliente: TestClient) -> None:
    cliente.fake.typing_names = ["Keller"]  # type: ignore[attr-defined]
    response = cliente.get(
        f"/api/conversations/{_CONVERSACION_ID}/typing", headers=_HEADERS
    )

    assert response.status_code == 200
    assert response.json() == {"typing": ["Keller"]}


def test_consulta_de_escritura_sin_sesion_responde_401(cliente: TestClient) -> None:
    response = cliente.get(f"/api/conversations/{_CONVERSACION_ID}/typing")

    assert response.status_code == 401
