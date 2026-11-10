"""
La limpieza de la BD de cada test de integración (`_suelta_la_bd_de_test`, BE #781).

Si un aviso en segundo plano no acaba en el tope, la limpieza se intenta igual y lo
que sale es el TimeoutError que lo nombra, no el error del DROP que ese aviso provoca
(«is being accessed by other users»), que escondería la causa.
"""

import asyncio

import pytest
import pytest_asyncio

from src.config import aviso_en_segundo_plano as avisos
from tests import conftest

pytestmark = pytest.mark.asyncio


class _Conexion:
    """La conexión del motor de administración: el DROP falla si se le dice."""

    def __init__(self, falla: Exception | None) -> None:
        self._falla = falla
        self.sentencias: list[str] = []

    async def __aenter__(self) -> "_Conexion":
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def execute(self, sentencia) -> None:
        """Apunta la sentencia; lanza el fallo si lo hay."""
        self.sentencias.append(str(sentencia))
        if self._falla is not None:
            raise self._falla


class _Motor:
    """Un motor falso que apunta si se cerró."""

    def __init__(self, falla: Exception | None = None) -> None:
        self.cerrado = False
        self.conexion = _Conexion(falla)

    def connect(self) -> _Conexion:
        """La conexión de administración."""
        return self.conexion

    async def dispose(self) -> None:
        """Se cierra."""
        self.cerrado = True


@pytest.fixture
def sustituciones(monkeypatch):
    """Las sustituciones de la app, en un diccionario propio para el test."""
    propias = {"algo": object()}
    monkeypatch.setattr(conftest.fastapi_app, "dependency_overrides", propias)
    return propias


@pytest_asyncio.fixture
async def aviso_colgado(monkeypatch):
    """Un aviso que no acaba, con un tope de espera de 0,1 s."""
    monkeypatch.setattr(conftest, "_ESPERA_MAXIMA_DEL_SEGUNDO_PLANO_S", 0.1)
    colgado = asyncio.create_task(asyncio.sleep(3600), name="aviso-colgado")
    avisos._PENDIENTES.add(colgado)
    colgado.add_done_callback(avisos._PENDIENTES.discard)
    yield colgado
    colgado.cancel()
    await asyncio.gather(colgado, return_exceptions=True)


async def test_a_hung_notice_raises_its_timeout_not_the_drop_error(sustituciones, aviso_colgado):
    """
    Given: Un aviso colgado con la conexión cogida, así que el DROP falla
    When: Se suelta la BD del test
    Then: Sale el TimeoutError que nombra el aviso (con el error del DROP como causa), y
          los motores se cierran y las sustituciones se quitan igual
    """
    admin, prueba = _Motor(falla=RuntimeError("is being accessed by other users")), _Motor()

    with pytest.raises(TimeoutError, match="aviso-colgado") as error:
        await conftest._suelta_la_bd_de_test(admin, prueba, "test_db_x")

    assert isinstance(error.value.__cause__, RuntimeError)
    assert prueba.cerrado and admin.cerrado
    assert sustituciones == {}


async def test_a_hung_notice_still_raises_when_the_drop_works(sustituciones, aviso_colgado):
    """
    Given: Un aviso colgado y un DROP que funciona
    When: Se suelta la BD del test
    Then: La BD se borra y aun así sale el TimeoutError: el aviso colgado no se calla
    """
    admin, prueba = _Motor(), _Motor()

    with pytest.raises(TimeoutError, match="aviso-colgado"):
        await conftest._suelta_la_bd_de_test(admin, prueba, "test_db_x")

    assert admin.conexion.sentencias == ["DROP DATABASE test_db_x"]


async def test_without_notices_a_drop_error_is_not_swallowed(sustituciones):
    """
    Given: Ningún aviso pendiente y un DROP que falla
    When: Se suelta la BD del test
    Then: Sale el error del DROP, y los motores se cierran igual
    """
    admin, prueba = _Motor(falla=RuntimeError("drop roto")), _Motor()

    with pytest.raises(RuntimeError, match="drop roto"):
        await conftest._suelta_la_bd_de_test(admin, prueba, "test_db_x")

    assert prueba.cerrado and admin.cerrado
    assert sustituciones == {}


async def test_without_notices_everything_is_released(sustituciones):
    """
    Given: Ningún aviso pendiente
    When: Se suelta la BD del test
    Then: Se borra, se cierran los motores y se quitan las sustituciones
    """
    admin, prueba = _Motor(), _Motor()

    await conftest._suelta_la_bd_de_test(admin, prueba, "test_db_x")

    assert admin.conexion.sentencias == ["DROP DATABASE test_db_x"]
    assert prueba.cerrado and admin.cerrado
    assert sustituciones == {}
