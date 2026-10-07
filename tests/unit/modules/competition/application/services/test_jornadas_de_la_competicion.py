"""
Las jornadas de un stroke play en horas absolutas (#251).

| Caso                                        | Resultado                                  |
|---------------------------------------------|--------------------------------------------|
| Dos franjas el mismo día                    | La primera salida es la de la mañana       |
| Dos campos con husos distintos el mismo día | Acaba en la medianoche más tardía          |
| Sesión sin hoja                             | No cuenta                                  |
"""

from datetime import UTC, date, datetime, time

import pytest

from src.modules.competition.application.services.jornadas_de_la_competicion import (
    JornadasDeLaCompeticion,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.shared.domain.value_objects.match_format import MatchFormat

pytestmark = pytest.mark.asyncio

VIERNES = date(2030, 10, 11)
MADRID = GolfCourseId.generate()
CANARIAS = GolfCourseId.generate()


class _Zonas:
    async def for_course(self, campo):
        return {MADRID: "Europe/Madrid", CANARIAS: "Atlantic/Canary"}[campo]


def _franja(campo, sesion, primera, ultima):
    return Round.create_franja(
        competition_id=CompetitionId.generate(),
        golf_course_id=campo,
        round_date=VIERNES,
        session_type=sesion,
        hoja_de_salidas=HojaDeSalidas(primera, ultima, 10, 4),
    )


async def test_la_primera_salida_es_la_de_la_manana():
    sesiones = [
        _franja(MADRID, SessionType.AFTERNOON, time(15, 0), time(17, 0)),
        _franja(MADRID, SessionType.MORNING, time(9, 0), time(11, 0)),
    ]

    (jornada,) = await JornadasDeLaCompeticion.de(sesiones, _Zonas())

    assert jornada.primera_salida == datetime(2030, 10, 11, 7, 0, tzinfo=UTC)


async def test_con_husos_distintos_acaba_en_la_medianoche_mas_tardia():
    # Canarias primero: la medianoche más tardía no puede ganar por ir la última
    sesiones = [
        _franja(CANARIAS, SessionType.AFTERNOON, time(15, 0), time(17, 0)),
        _franja(MADRID, SessionType.MORNING, time(9, 0), time(11, 0)),
    ]

    (jornada,) = await JornadasDeLaCompeticion.de(sesiones, _Zonas())

    # Medianoche en Canarias (UTC+1 en octubre) es más tarde que en Madrid (UTC+2)
    assert jornada.fin == datetime(2030, 10, 11, 23, 0, tzinfo=UTC)


async def test_una_sesion_sin_hoja_no_cuenta():
    ryder = Round.create(
        competition_id=CompetitionId.generate(),
        golf_course_id=MADRID,
        round_date=VIERNES,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )

    assert await JornadasDeLaCompeticion.de([ryder], _Zonas()) == []
