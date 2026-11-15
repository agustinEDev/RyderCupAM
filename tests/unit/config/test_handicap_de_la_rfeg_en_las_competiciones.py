"""
La RFEG da el hándicap desde el perfil: sus competiciones se enteran (D1 y D4, 16 nov 2026).

| Caso                         | Resultado                                                  |
|------------------------------|------------------------------------------------------------|
| La RFEG lo da                | El caso de uso de competición corre con su valor, en Decimal |
| El caso de uso falla         | No sale de aquí: el perfil ya está guardado                |
| Los dos caminos del perfil   | Llevan el aviso montado (/update y /refresh-mine)          |
| Con Actividad (D3)           | El caso de uso recibe cómo montarla, sin montarla todavía  |
"""

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import refresco_de_handicaps
from src.config.dependencies import usuarios
from src.config.dependencies.comun import actividad_en_sesion_propia
from src.config.refresco_de_handicaps import HandicapDeLaRfegEnLasCompeticiones
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class _CasoQueApunta:
    ejecutados: ClassVar[list] = []
    falla = False

    def __init__(self, herramientas, reloj, actividad=None):
        self.herramientas, self.reloj, self.actividad = herramientas, reloj, actividad

    async def execute(self, user_id, handicap):
        if _CasoQueApunta.falla:
            raise RuntimeError("competiciones caidas")
        _CasoQueApunta.ejecutados.append((user_id, handicap, self.herramientas, self.actividad))


@pytest.fixture
def caso(monkeypatch):
    _CasoQueApunta.ejecutados = []
    _CasoQueApunta.falla = False
    monkeypatch.setattr(refresco_de_handicaps, "HandicapDeLaRfegDelPerfilUseCase", _CasoQueApunta)
    return _CasoQueApunta


async def test_corre_el_caso_de_uso_con_su_valor(caso):
    """Given la RFEG da 13.2 When se avisa Then corre el de competición con Decimal('13.2')."""

    user_id = UserId.generate()

    await HandicapDeLaRfegEnLasCompeticiones(MagicMock()).encontrado(user_id, 13.2)

    [(quien, valor, herramientas, _)] = caso.ejecutados
    assert (quien, valor) == (user_id, Decimal("13.2"))
    assert callable(herramientas)


async def test_si_falla_no_sale_de_aqui(caso):
    """Given el caso de uso falla When se avisa Then no lanza: el perfil ya está guardado."""
    caso.falla = True

    await HandicapDeLaRfegEnLasCompeticiones(MagicMock()).encontrado(UserId.generate(), 13.2)


@pytest.mark.parametrize(
    "proveedor", ["get_update_handicap_use_case", "get_refresh_own_handicap_use_case"]
)
def test_los_dos_caminos_del_perfil_lo_llevan(proveedor):
    """Given los proveedores del perfil When se montan Then llevan el aviso a las competiciones."""
    fabrica = MagicMock()

    caso_de_uso = getattr(usuarios, proveedor)(MagicMock(), AsyncMock(), fabrica)

    assert isinstance(caso_de_uso._al_encontrarlo, HandicapDeLaRfegEnLasCompeticiones)
    assert caso_de_uso._al_encontrarlo._fabrica is fabrica
    assert caso_de_uso._al_encontrarlo._actividad is actividad_en_sesion_propia


class _Fabrica:
    def __init__(self):
        self.abiertas: list[object] = []

    @asynccontextmanager
    async def __call__(self):
        sesion = object()
        self.abiertas.append(sesion)
        yield sesion


async def test_con_actividad_el_caso_de_uso_recibe_como_montarla(caso):
    """
    Given el aviso con Actividad
    When la RFEG lo da
    Then el caso de uso recibe cómo montarla sobre su sesión, sin montarla aún (D3, T1)
    """
    fabrica = _Fabrica()
    montadas: list[object] = []

    def construir(sesion):
        montadas.append(sesion)
        return "publicador"

    await HandicapDeLaRfegEnLasCompeticiones(fabrica, actividad=construir).encontrado(
        UserId.generate(), 13.0
    )

    [(_, _, _, montar)] = caso.ejecutados
    assert fabrica.abiertas == []
    async with montar() as publicador:
        assert publicador == "publicador"
    assert montadas == fabrica.abiertas


async def test_sin_actividad_no_la_recibe(caso):
    """Given el aviso sin Actividad When la RFEG lo da Then el caso de uso no la recibe."""
    await HandicapDeLaRfegEnLasCompeticiones(_Fabrica()).encontrado(UserId.generate(), 13.0)

    assert caso.ejecutados[0][3] is None
