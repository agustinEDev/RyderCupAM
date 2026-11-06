"""
El aviso de nuevo inicio de sesión, en segundo plano (BE #737).

  #   caso                                   | esperado
  ----|-------------------------------------|----------------------------------------
  B1  toca avisar                            | el login no espera: la tarea queda en
                                             |   marcha y apuntada hasta que acaba
  B2  no toca (sin confirmar, alta, conocido) | ni se lanza
  B3  la tarea falla                         | no sube
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
