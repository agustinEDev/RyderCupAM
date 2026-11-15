"""
La RFEG da el hándicap desde el perfil: sus competiciones se enteran (D1, D4; R5-R8).

| Caso | Situación                         | Resultado                                                   |
|------|-----------------------------------|-------------------------------------------------------------|
| R6   | La RFEG lo da                     | Se lanza en segundo plano: la respuesta no espera            |
| R6   | La tarea corre                    | El de competición, con su valor en Decimal y Actividad       |
| R8   | El de competición falla           | Una sola vez al log, y no sale de la tarea                   |
| R6   | Se apaga la app                   | La tarea cuenta entre las que se esperan                     |
| R5   | Refresco apagado (o en los tests) | No hay aviso: los proveedores no lo llevan                    |
| R5   | Refresco encendido                | El aviso va con el lanzador del proceso                      |
| R7   | Los tres caminos con la RFEG      | /update, /refresh-mine y varios a la vez lo llevan           |
"""

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import refresco_de_handicaps
from src.config.dependencies import comun, usuarios
from src.config.dependencies.comun import actividad_en_sesion_propia
from src.config.refresco_de_handicaps import (
    HandicapDeLaRfegEnLasCompeticiones,
    LanzadorEnSegundoPlano,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class _CasoQueApunta:
    ejecutados: ClassVar[list] = []
    falla = False
    soltar: asyncio.Event | None = None

    def __init__(self, herramientas, reloj, actividad=None):
        self.herramientas, self.reloj, self.actividad = herramientas, reloj, actividad

    async def execute(self, user_id, handicap):
        if _CasoQueApunta.soltar is not None:
            await _CasoQueApunta.soltar.wait()
        if _CasoQueApunta.falla:
            raise RuntimeError("competiciones caidas")
        _CasoQueApunta.ejecutados.append((user_id, handicap, self.herramientas, self.actividad))


@pytest.fixture
def caso(monkeypatch):
    _CasoQueApunta.ejecutados = []
    _CasoQueApunta.falla = False
    _CasoQueApunta.soltar = None
    monkeypatch.setattr(refresco_de_handicaps, "HandicapDeLaRfegDelPerfilUseCase", _CasoQueApunta)
    return _CasoQueApunta


class _Fabrica:
    def __init__(self):
        self.abiertas: list[object] = []

    @asynccontextmanager
    async def __call__(self):
        sesion = object()
        self.abiertas.append(sesion)
        yield sesion


def _lanzador(fabrica=None, actividad=None) -> LanzadorEnSegundoPlano:
    return LanzadorEnSegundoPlano(
        fabrica or _Fabrica(), MagicMock(), MagicMock(), actividad=actividad
    )


async def test_no_espera_a_las_competiciones(caso):
    """
    Given el de competición todavía esperando
    When la RFEG lo da
    Then el aviso vuelve ya, y la tarea queda en marcha hasta que acaba (R6)
    """
    caso.soltar = asyncio.Event()
    lanzador = _lanzador()

    # Si esperara a las competiciones, no volvería nunca: se corta al segundo
    await asyncio.wait_for(
        HandicapDeLaRfegEnLasCompeticiones(lanzador).encontrado(UserId.generate(), 13.2), 1
    )

    assert caso.ejecutados == []
    assert len(lanzador.tareas_en_marcha()) == 1
    caso.soltar.set()
    await lanzador.esperar_a_todas()
    assert len(caso.ejecutados) == 1
    assert lanzador.tareas_en_marcha() == []


async def test_corre_con_su_valor_y_actividad_sin_montar(caso):
    """
    Given el lanzador con Actividad
    When la tarea corre
    Then el de competición recibe su valor en Decimal y cómo montar Actividad, sin montarla
    """
    fabrica = _Fabrica()
    montadas: list[object] = []

    def construir(sesion):
        montadas.append(sesion)
        return "publicador"

    lanzador = _lanzador(fabrica, actividad=construir)
    user_id = UserId.generate()

    await HandicapDeLaRfegEnLasCompeticiones(lanzador).encontrado(user_id, 13.2)
    await lanzador.esperar_a_todas()

    [(quien, valor, herramientas, montar)] = caso.ejecutados
    assert (quien, valor) == (user_id, Decimal("13.2"))
    assert callable(herramientas)
    assert fabrica.abiertas == []
    async with montar() as publicador:
        assert publicador == "publicador"
    assert montadas == fabrica.abiertas


async def test_sin_actividad_no_la_recibe(caso):
    """Given el lanzador sin Actividad When corre Then el de competición no la recibe."""
    lanzador = _lanzador()

    await HandicapDeLaRfegEnLasCompeticiones(lanzador).encontrado(UserId.generate(), 13.0)
    await lanzador.esperar_a_todas()

    assert caso.ejecutados[0][3] is None


async def test_si_falla_una_vez_al_log_y_no_sale(caso, caplog):
    """Given el de competición falla When corre Then una sola línea en el log, sin excepción (R8)."""
    caso.falla = True
    lanzador = _lanzador()

    await HandicapDeLaRfegEnLasCompeticiones(lanzador).encontrado(UserId.generate(), 13.0)
    await lanzador.esperar_a_todas()

    errores = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(errores) == 1
    assert all(t.exception() is None for t in lanzador._tareas) or lanzador._tareas == set()


def test_apagado_no_hay_aviso(monkeypatch):
    """Given el refresco apagado When se pide el aviso Then no hay (R5)."""
    monkeypatch.setattr(comun, "_lanzador", None)
    monkeypatch.setattr(comun, "refresco_activado", lambda _entorno: False)

    assert comun.get_aviso_de_la_rfeg() is None


def test_encendido_va_con_el_lanzador_del_proceso(monkeypatch):
    """Given el refresco encendido When se pide el aviso Then va con el lanzador de siempre (R5)."""
    monkeypatch.setattr(comun, "_lanzador", None)
    monkeypatch.setattr(comun, "refresco_activado", lambda _entorno: True)
    monkeypatch.setattr(comun, "RFEGHandicapService", MagicMock())
    monkeypatch.setattr(comun, "EmailService", MagicMock())

    aviso = comun.get_aviso_de_la_rfeg()

    assert isinstance(aviso, HandicapDeLaRfegEnLasCompeticiones)
    assert aviso._lanzador is comun.get_lanzador_de_actualizaciones()
    assert aviso._lanzador._actividad is actividad_en_sesion_propia


@pytest.mark.parametrize(
    "proveedor",
    [
        "get_update_handicap_use_case",
        "get_refresh_own_handicap_use_case",
        "get_update_multiple_handicaps_use_case",
    ],
)
def test_los_caminos_con_la_rfeg_lo_llevan(proveedor):
    """Given los proveedores que preguntan a la RFEG When se montan Then llevan el aviso (R7)."""
    aviso = MagicMock()

    caso_de_uso = getattr(usuarios, proveedor)(MagicMock(), AsyncMock(), aviso)

    assert caso_de_uso._al_encontrarlo is aviso
