"""
La pasada de hándicaps en segundo plano avisa en Actividad (15 nov 2026, H2 y H3).

| Caso                                  | Resultado                                              |
|---------------------------------------|--------------------------------------------------------|
| Con Actividad                         | La pasada recibe cómo montarla; no se monta antes (T1) |
| Montarla falla                        | La pasada corre igual (T1)                             |
| Sin Actividad                         | La pasada no la recibe, y no se abre ninguna sesión    |
| En producción                         | El lanzador del proceso lleva la de verdad             |
"""

from contextlib import asynccontextmanager
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import refresco_de_handicaps
from src.config.dependencies import comun
from src.config.dependencies.comun import actividad_en_sesion_propia
from src.config.refresco_de_handicaps import LanzadorEnSegundoPlano

pytestmark = pytest.mark.asyncio


class _Fabrica:
    """Las sesiones que se abren, y cuántas siguen abiertas."""

    def __init__(self):
        self.abiertas: list[object] = []
        self.cerradas = 0

    @asynccontextmanager
    async def __call__(self):
        sesion = object()
        self.abiertas.append(sesion)
        try:
            yield sesion
        finally:
            self.cerradas += 1


class _CasoQueApunta:
    """El caso de uso de la pasada, apuntando con qué Actividad se creó."""

    creados: ClassVar[list[dict]] = []

    def __init__(self, **kwargs):
        _CasoQueApunta.creados.append(kwargs)

    async def execute(self, _update_id):
        return 0


@pytest.fixture
def caso(monkeypatch):
    _CasoQueApunta.creados = []
    monkeypatch.setattr(refresco_de_handicaps, "RefrescarHandicapsUseCase", _CasoQueApunta)
    return _CasoQueApunta


async def test_con_actividad_la_pasada_recibe_como_montarla_y_no_se_monta_antes(caso):
    """
    Given un lanzador con Actividad
    When pasa una actualización
    Then la pasada recibe cómo montarla, sin que se haya abierto ninguna sesión todavía (T1)
    """
    fabrica = _Fabrica()
    montadas: list[object] = []

    def actividad(sesion):
        montadas.append(sesion)
        return f"actividad sobre {id(sesion)}"

    lanzador = LanzadorEnSegundoPlano(fabrica, MagicMock(), MagicMock(), actividad=actividad)

    await lanzador.pasada(MagicMock())

    assert fabrica.abiertas == []
    montar = caso.creados[0]["actividad"]
    async with montar() as publicador:
        assert publicador == f"actividad sobre {id(montadas[0])}"
        assert montadas == fabrica.abiertas
    assert fabrica.cerradas == 1


async def test_si_montarla_falla_la_pasada_ya_corrio(caso):
    """
    Given un lanzador cuya Actividad falla al montarse
    When pasa una actualización
    Then la pasada corre igual y dice lo suyo: montarla es cosa de la pasada, al avisar (T1)
    """

    def actividad(_sesion):
        raise RuntimeError("actividad caida")

    resultado = await LanzadorEnSegundoPlano(
        _Fabrica(), MagicMock(), MagicMock(), actividad=actividad
    ).pasada(MagicMock())

    assert resultado == 0


async def test_sin_actividad_no_la_recibe(caso):
    """Given un lanzador sin Actividad When pasa Then la pasada no la recibe ni abre sesión."""
    fabrica = _Fabrica()

    await LanzadorEnSegundoPlano(fabrica, MagicMock(), MagicMock()).pasada(MagicMock())

    assert caso.creados[0]["actividad"] is None
    assert fabrica.abiertas == []


def test_en_produccion_el_lanzador_lleva_la_de_verdad(monkeypatch):
    """
    Given el refresco encendido
    When se pide el lanzador del proceso
    Then lleva la Actividad de verdad
    """
    monkeypatch.setattr(comun, "_lanzador", None)
    monkeypatch.setattr(comun, "refresco_activado", lambda _entorno: True)
    monkeypatch.setattr(comun, "RFEGHandicapService", MagicMock())
    monkeypatch.setattr(comun, "EmailService", MagicMock())

    lanzador = comun.get_lanzador_de_actualizaciones()

    assert lanzador._actividad is actividad_en_sesion_propia


def test_la_de_verdad_monta_el_publicador_de_actividad():
    """Given una sesión When se monta Actividad Then es el publicador de competición."""
    from src.modules.social.infrastructure.adapters.competition_activity_publisher import (
        CompetitionActivityPublisher,
    )

    sesion = MagicMock()
    sesion.execute = AsyncMock()

    assert isinstance(actividad_en_sesion_propia(sesion), CompetitionActivityPublisher)
