"""Pruebas del registro efímero de «escribiendo…» (puente REST).

La señal caduca sola a los cinco segundos (Q77/Q96), se retira con
`is_typing=False` y nunca incluye al propio actor en la consulta.
"""

import time
from uuid import uuid4

from Chatly.backend.services.typing_registry import TypingRegistry


def test_la_senal_aparece_y_caduca_tras_el_ttl() -> None:
    registro = TypingRegistry(ttl_seconds=0.05)
    conversacion = uuid4()
    usuario = uuid4()
    otro = uuid4()

    registro.record_typing(conversacion, usuario)
    assert registro.typing_members(conversacion, exclude_user_id=otro) == [usuario]

    time.sleep(0.08)
    assert registro.typing_members(conversacion, exclude_user_id=otro) == []


def test_is_typing_false_retira_la_senal() -> None:
    registro = TypingRegistry()
    conversacion = uuid4()
    usuario = uuid4()

    registro.record_typing(conversacion, usuario)
    registro.record_typing(conversacion, usuario, is_typing=False)

    assert registro.typing_members(conversacion, exclude_user_id=uuid4()) == []


def test_la_consulta_excluye_al_propio_actor() -> None:
    registro = TypingRegistry()
    conversacion = uuid4()
    usuario = uuid4()

    registro.record_typing(conversacion, usuario)

    assert registro.typing_members(conversacion, exclude_user_id=usuario) == []


def test_las_conversaciones_no_se_mezclan() -> None:
    registro = TypingRegistry()
    conversacion = uuid4()
    otra = uuid4()
    usuario = uuid4()

    registro.record_typing(conversacion, usuario)

    assert registro.typing_members(otra, exclude_user_id=uuid4()) == []


def test_dos_usuarios_escribiendo_se_listan_juntos() -> None:
    registro = TypingRegistry()
    conversacion = uuid4()
    ana = uuid4()
    bruno = uuid4()

    registro.record_typing(conversacion, ana)
    registro.record_typing(conversacion, bruno)

    miembros = registro.typing_members(conversacion, exclude_user_id=uuid4())
    assert sorted(miembros) == sorted([ana, bruno])
