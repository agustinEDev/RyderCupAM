"""
El aviso de nuevo inicio de sesión, en segundo plano (BE #737).

  #   caso                                   | esperado
  ----|-------------------------------------|----------------------------------------
  B1  toca avisar                            | el login no espera: la tarea queda en
                                             |   marcha y apuntada hasta que acaba
  B2  no toca (sin confirmar, alta, conocido) | ni se lanza
  B3  la tarea falla                         | no sube
  B4  una tarea de un bucle ya cerrado       | se descarta: no rompe la espera (#781)
  B5  una tarea que no acaba en el tope      | TimeoutError con su nombre (#781)
  B6  una tarea de otro bucle aún abierto     | no se espera ni rompe la espera (#781)
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.config import aviso_en_segundo_plano as modulo
from src.config.aviso_en_segundo_plano import AvisoEnSegundoPlano, espera_los_avisos_pendientes
from src.modules.user.application.dto.device_dto import AvisoDeNuevoInicioRequestDTO

pytestmark = pytest.mark.asyncio


def _fabrica(puerta: asyncio.Event, abiertas: list):
    @asynccontextmanager
    async def abre():
        abiertas.append(1)
        await puerta.wait()
        raise RuntimeError("sin BD en el test")
        yield  # pragma: no cover

    return abre


async def _avisa(aviso, **extra):
    datos = {"desconocido": True, "verificado": True, "es_alta": False} | extra
    await aviso.avisa(
        AvisoDeNuevoInicioRequestDTO(
            user_id=str(uuid4()),
            email="ana@example.com",
            nombre="Ana",
            device_id=str(uuid4()),
            **datos,
        )
    )


async def test_b1_the_login_does_not_wait_and_the_task_is_kept_until_it_ends():
    """
    Given: Un aviso que toca enviar y una BD que tarda
    When: El login lo pide
    Then: Vuelve enseguida, la tarea queda apuntada mientras corre, y al acabar se suelta
    """
    puerta, abiertas = asyncio.Event(), []
    aviso = AvisoEnSegundoPlano(_fabrica(puerta, abiertas), AsyncMock())

    await _avisa(aviso)

    assert len(modulo._PENDIENTES) == 1
    await asyncio.sleep(0)
    assert abiertas == [1]
    puerta.set()
    await espera_los_avisos_pendientes()
    assert set() == modulo._PENDIENTES


@pytest.mark.parametrize(
    "extra", [{"verificado": False}, {"es_alta": True}, {"desconocido": False}]
)
async def test_b2_when_there_is_nothing_to_notify_no_task_is_started(extra):
    """
    Given: Un correo sin confirmar, el alta o un dispositivo conocido
    When: El login lo pide
    Then: No se lanza ninguna tarea
    """
    puerta, abiertas = asyncio.Event(), []
    aviso = AvisoEnSegundoPlano(_fabrica(puerta, abiertas), AsyncMock())

    await _avisa(aviso, **extra)

    assert set() == modulo._PENDIENTES
    assert abiertas == []


async def test_b3_a_failing_task_does_not_raise():
    """
    Given: La BD falla en la tarea
    When: Se espera a que acabe
    Then: No sube nada
    """
    puerta, abiertas = asyncio.Event(), []
    puerta.set()
    aviso = AvisoEnSegundoPlano(_fabrica(puerta, abiertas), AsyncMock())

    await _avisa(aviso)
    await espera_los_avisos_pendientes()

    assert abiertas == [1]


def _tarea_de_un_bucle_cerrado() -> asyncio.Task:
    """
    Una tarea sin acabar de otro bucle de eventos, ya cerrado (un test anterior). Se
    crea en otro hilo: en este ya corre el bucle del test.
    """
    import threading

    creada: list[asyncio.Task] = []

    def _en_otro_hilo() -> None:
        otro = asyncio.new_event_loop()
        creada.append(otro.create_task(asyncio.sleep(3600), name="aviso-de-otro-test"))
        otro.run_until_complete(asyncio.sleep(0))
        otro.close()

    hilo = threading.Thread(target=_en_otro_hilo)
    hilo.start()
    hilo.join()
    return creada[0]


async def test_b4_a_task_from_a_closed_loop_is_discarded():
    """
    Given: En la lista de pendientes, una tarea de un bucle ya cerrado (un test anterior
           que no la esperó) y otra del bucle actual
    When: Se espera a los avisos pendientes
    Then: Se espera la del bucle actual y la otra se descarta, sin RuntimeError por ser
          de otro bucle: si no, todos los teardowns siguientes del worker fallarían
    """
    vieja = _tarea_de_un_bucle_cerrado()
    modulo._PENDIENTES.add(vieja)
    actual = asyncio.create_task(asyncio.sleep(0.01))
    modulo._PENDIENTES.add(actual)
    actual.add_done_callback(modulo._PENDIENTES.discard)

    await espera_los_avisos_pendientes()

    assert actual.done()
    assert set() == modulo._PENDIENTES


async def test_b5_a_task_that_does_not_end_in_time_raises_with_its_name():
    """
    Given: Un aviso que no acaba
    When: Se espera con un tope de 0,1 s
    Then: TimeoutError que lo nombra; la tarea no se cancela ni se pierde de la lista
    """
    colgada = asyncio.create_task(asyncio.sleep(3600), name="aviso-colgado")
    modulo._PENDIENTES.add(colgada)
    colgada.add_done_callback(modulo._PENDIENTES.discard)

    try:
        with pytest.raises(TimeoutError, match="aviso-colgado"):
            await espera_los_avisos_pendientes(tope_s=0.1)
        assert not colgada.done()
        assert colgada in modulo._PENDIENTES
    finally:
        colgada.cancel()
        await asyncio.gather(colgada, return_exceptions=True)


async def test_b6_a_task_from_another_open_loop_is_left_alone():
    """
    Given: Una tarea sin acabar de otro bucle que sigue abierto (en otro hilo)
    When: Se espera a los avisos pendientes de este bucle
    Then: Vuelve sin esperarla ni fallar por ser de otro bucle, y no la quita de la
          lista: es de quien corre ese bucle
    """
    import threading

    otro = asyncio.new_event_loop()
    hilo = threading.Thread(target=otro.run_forever)
    hilo.start()
    try:
        ajena = asyncio.run_coroutine_threadsafe(_crea_tarea_colgada(), otro).result(timeout=5)
        modulo._PENDIENTES.add(ajena)

        await asyncio.wait_for(espera_los_avisos_pendientes(), timeout=2)

        assert ajena in modulo._PENDIENTES
    finally:
        modulo._PENDIENTES.discard(ajena)
        otro.call_soon_threadsafe(ajena.cancel)
        otro.call_soon_threadsafe(otro.stop)
        hilo.join()
        otro.close()


async def _crea_tarea_colgada() -> asyncio.Task:
    """Crea, en el bucle donde corre, una tarea que no acaba."""
    return asyncio.create_task(asyncio.sleep(3600), name="aviso-de-otro-bucle")
