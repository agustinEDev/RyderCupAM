"""
El cierre de inscripciones por el plazo, como tarea del proceso (15 nov 2026).

| Caso | Situación                                  | Qué pasa                                        |
|------|--------------------------------------------|-------------------------------------------------|
| C3   | cada hora                                  | una vuelta, y espera una hora                   |
| C3   | una vuelta que revienta                    | la siguiente se hace igual                      |
| C3   | la app se apaga                            | la tarea se cancela, sin tragárselo             |
| C3   | en los tests (TESTING=true)                | apagado; en PRO y en el Kind, encendido         |
| C3   | otro proceso con el candado                | no hace la vuelta                               |
| C3   | su candado                                 | distinto del de las partidas rápidas            |
"""

import asyncio

import pytest

from src.config import cierre_de_inscripciones as modulo
from src.config.cierre_de_inscripciones import (
    CANDADO_DEL_CIERRE_DE_INSCRIPCIONES,
    INTERVALO_SEGUNDOS,
    CierreDeInscripciones,
    cierre_de_inscripciones_activado,
)
from src.config.cierre_de_partidas_rapidas import CANDADO_DEL_CIERRE
from src.config.refresco_de_handicaps import CANDADO_DEL_VIGILANTE


class _FinError(Exception):
    """Para salir del bucle en el test."""


class _Esperas:
    def __init__(self, vueltas: int):
        self.esperas: list[float] = []
        self._vueltas = vueltas

    async def __call__(self, segundos: float) -> None:
        self.esperas.append(segundos)
        if len(self.esperas) >= self._vueltas:
            raise _FinError()


class _Fabrica:
    def __init__(self):
        self.kw = {"bind": object()}


@pytest.mark.asyncio
async def test_cada_hora_una_vuelta_y_una_que_revienta_no_para_las_demas(monkeypatch):
    """
    C3. Given una primera vuelta que revienta
    When la tarea vigila
    Then espera una hora y hace la segunda igual
    """
    vueltas: list[int] = []

    async def vuelta(self):
        vueltas.append(1)
        if len(vueltas) == 1:
            raise RuntimeError("se cayó la base")

    monkeypatch.setattr(CierreDeInscripciones, "vuelta", vuelta)
    esperas = _Esperas(vueltas=2)

    with pytest.raises(_FinError):
        await CierreDeInscripciones(_Fabrica(), esperar=esperas).vigilar()

    assert len(vueltas) == 2
    assert esperas.esperas == [INTERVALO_SEGUNDOS, INTERVALO_SEGUNDOS]
    assert INTERVALO_SEGUNDOS == 60 * 60


@pytest.mark.asyncio
async def test_al_apagarse_la_app_la_tarea_se_cancela(monkeypatch):
    """C3. Given la app apagándose / When se cancela la vuelta / Then se propaga."""

    async def vuelta(self):
        raise asyncio.CancelledError()

    monkeypatch.setattr(CierreDeInscripciones, "vuelta", vuelta)

    with pytest.raises(asyncio.CancelledError):
        await CierreDeInscripciones(_Fabrica(), esperar=_Esperas(vueltas=5)).vigilar()


@pytest.mark.parametrize(
    ("entorno", "encendido"),
    [
        ({}, True),
        ({"TESTING": "false"}, True),
        ({"TESTING": "true"}, False),
        ({"TESTING": "TRUE"}, False),
    ],
)
def test_apagado_solo_en_los_tests(entorno, encendido):
    """C3. Given el entorno / Then encendido salvo con TESTING=true."""
    assert cierre_de_inscripciones_activado(entorno) is encendido


@pytest.mark.asyncio
async def test_con_el_candado_de_otro_no_hace_la_vuelta(monkeypatch):
    """C3. Given otro proceso con el candado / When toca la vuelta / Then None, sin cerrar nada."""
    pedidos: list[int] = []

    async def con_candado(motor, clave, trabajo):
        pedidos.append(clave)

    async def cierra(self):
        raise AssertionError("no debía cerrar nada")

    monkeypatch.setattr(modulo, "con_candado", con_candado)
    monkeypatch.setattr(CierreDeInscripciones, "_cierra", cierra)

    assert await CierreDeInscripciones(_Fabrica()).vuelta() is None
    assert pedidos == [CANDADO_DEL_CIERRE_DE_INSCRIPCIONES]


def test_su_candado_es_suyo():
    """C3. Given los candados de las tareas / Then el del cierre de inscripciones es otro."""
    assert CANDADO_DEL_CIERRE_DE_INSCRIPCIONES not in (CANDADO_DEL_CIERRE, CANDADO_DEL_VIGILANTE)
