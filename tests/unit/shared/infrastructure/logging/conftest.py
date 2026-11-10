"""Fixtures de los tests del log de seguridad."""

import pytest

from tests.unit.shared.infrastructure.logging._hilos_del_log import (
    vacia_todos_los_hilos_del_log,
)


@pytest.fixture(autouse=True)
def _sin_eventos_de_otros_tests(capsys):
    """
    Cada SecurityLogger escribe desde su propio hilo, en la salida estándar que esté
    activa al escribir. Un evento que un test anterior dejó en la cola podía escribirse
    tarde, dentro de la captura del test siguiente, y descuadrar cuántas líneas hay
    (fallo intermitente en el CI). Antes de cada test se vacían todos los hilos vivos y
    se descarta lo capturado hasta entonces.
    """
    vacia_todos_los_hilos_del_log()
    capsys.readouterr()
