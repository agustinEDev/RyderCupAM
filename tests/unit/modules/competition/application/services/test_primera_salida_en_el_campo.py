"""
La primera salida de una franja con el desfase del campo (FE #824, BE #537).

| Caso                                   | Resultado                           |
|----------------------------------------|-------------------------------------|
| Campo en Madrid                        | 09:00+02:00 (el instante de siempre) |
| El campo pierde su zona a media lectura | ZonaDesconocidaError, no la del servidor |
| O la recupera (la 1.ª lectura sin zona)  | ZonaDesconocidaError, tampoco la del servidor |
"""

from datetime import UTC, datetime, time

import pytest

from src.modules.competition.application.services.jornadas_de_la_competicion import (
    ZonaDesconocidaError,
)
from src.modules.competition.application.services.vista_de_la_franja import (
    primera_salida_en_el_campo,
)
from src.modules.competition.domain.value_objects.session_type import SessionType
from tests.unit.modules.competition.application.services.test_jornadas_de_la_competicion import (
    MADRID,
    _franja,
    _Zonas,
)

pytestmark = pytest.mark.asyncio


async def test_con_el_desfase_del_campo():
    franja = _franja(MADRID, SessionType.MORNING, time(9, 0), time(11, 50))

    abre = await primera_salida_en_el_campo(franja, _Zonas())

    assert abre.isoformat() == "2030-10-11T09:00:00+02:00"
    assert abre == datetime(2030, 10, 11, 7, 0, tzinfo=UTC)


class _ZonaQueSePierde:
    """La primera lectura tiene zona; las siguientes, no (CodeRabbit)."""

    def __init__(self):
        self.lecturas = 0

    async def for_course(self, campo):
        self.lecturas += 1
        return "Europe/Madrid" if self.lecturas == 1 else None


async def test_si_el_campo_pierde_la_zona_a_media_lectura_no_usa_la_del_servidor():
    franja = _franja(MADRID, SessionType.MORNING, time(9, 0), time(11, 50))

    with pytest.raises(ZonaDesconocidaError):
        await primera_salida_en_el_campo(franja, _ZonaQueSePierde())


class _ZonaQueLlegaTarde:
    """La primera lectura no tiene zona; la siguiente, sí (CodeRabbit)."""

    def __init__(self):
        self.lecturas = 0

    async def for_course(self, campo):
        self.lecturas += 1
        return None if self.lecturas == 1 else "Europe/Madrid"


async def test_si_la_primera_lectura_viene_sin_zona_tampoco_usa_la_del_servidor():
    franja = _franja(MADRID, SessionType.MORNING, time(9, 0), time(11, 50))

    with pytest.raises(ZonaDesconocidaError):
        await primera_salida_en_el_campo(franja, _ZonaQueLlegaTarde())
