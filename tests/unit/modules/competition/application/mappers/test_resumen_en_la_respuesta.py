"""
La tarjeta de «Mis competiciones» en la respuesta de cada competición (FE #846).

| Caso                                         | Resultado                                     |
|----------------------------------------------|-----------------------------------------------|
| Con dos campos                               | Los dos, en su orden, con nombre y país       |
| Sin campos                                   | []                                            |
| Stroke play de un día con dos franjas        | 1 jornada                                     |
| Ryder                                        | Jornadas null                                 |
| Inscrito y aprobado, con partida             | Su próxima salida, con la hora en HH:MM       |
| Sin inscribir (organiza y no juega)          | Sin próxima salida                            |
| Inscripción pendiente                        | Sin próxima salida                            |
| Un listado de varias                         | Los campos de todas en una sola lectura       |
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.campo_de_la_competicion import (
    CampoDeLaCompeticion,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.test_generar_partidas_use_case import (
    VIERNES,
    _Escenario,
)

pytestmark = pytest.mark.asyncio

EL_PRAT = CampoDeLaCompeticion(
    GolfCourseId.generate(), "Real Club de Golf El Prat", CountryCode("ES")
)
MEIS = CampoDeLaCompeticion(GolfCourseId.generate(), "Golf Meis", CountryCode("ES"))


async def _dto(escenario, quien):
    return await CompetitionDTOMapper.to_response_dto(escenario.competicion, quien, escenario.uow)


async def test_its_courses_in_order_with_name_and_country():
    escenario = _Escenario()
    await escenario.guardar()
    escenario.uow.competitions.con_campos(escenario.competicion.id, [MEIS, EL_PRAT])

    dto = await _dto(escenario, escenario.creador)

    assert [(c.id, c.name, c.country_code) for c in dto.golf_courses] == [
        (MEIS.golf_course_id.value, "Golf Meis", "ES"),
        (EL_PRAT.golf_course_id.value, "Real Club de Golf El Prat", "ES"),
    ]


async def test_without_courses_an_empty_list():
    escenario = _Escenario()
    await escenario.guardar()

    assert (await _dto(escenario, escenario.creador)).golf_courses == []


async def test_a_one_day_stroke_play_with_two_windows_is_one_playing_day():
    escenario = _Escenario()
    await escenario.guardar()

    assert (await _dto(escenario, escenario.creador)).playing_days == 1


async def test_a_ryder_cup_has_no_playing_days():
    escenario = _Escenario()
    escenario.competicion = Competition.create(
        id=CompetitionId.generate(),
        creator_id=escenario.creador,
        name=CompetitionName("Ryder de octubre"),
        dates=DateRange(VIERNES, VIERNES),
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        team_1_name="Europa",
        team_2_name="América",
    )
    async with escenario.uow:
        await escenario.uow.competitions.add(escenario.competicion)

    dto = await _dto(escenario, escenario.creador)

    assert (dto.playing_days, dto.my_next_session) == (None, None)


async def test_an_approved_player_with_a_group_gets_the_tee_time_as_hh_mm():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    await escenario.generar()

    salida = (await _dto(escenario, yo)).my_next_session

    assert (salida.date, salida.session_type, salida.tee_time) == (VIERNES, "MORNING", "09:00")


async def test_who_is_not_enrolled_has_no_next_session():
    escenario = _Escenario()
    await escenario.guardar()
    await escenario.con_plaza("9.0")
    await escenario.con_plaza("8.0")
    await escenario.generar()

    assert (await _dto(escenario, escenario.creador)).my_next_session is None


async def test_a_pending_enrollment_has_no_next_session():
    escenario = _Escenario()
    await escenario.guardar()
    yo = await escenario.con_plaza("9.0", status=EnrollmentStatus.REQUESTED)

    assert (await _dto(escenario, yo)).my_next_session is None


async def test_a_list_reads_the_courses_of_all_at_once():
    escenario = _Escenario()
    await escenario.guardar()
    otra = _Escenario().competicion
    async with escenario.uow:
        await escenario.uow.competitions.add(otra)
    escenario.uow.competitions.con_campos(escenario.competicion.id, [MEIS])
    escenario.uow.competitions.con_campos(otra.id, [EL_PRAT])
    lecturas = []
    leer = escenario.uow.competitions.campos_de

    async def contando(ids):
        lecturas.append(list(ids))
        return await leer(ids)

    escenario.uow.competitions.campos_de = contando

    dtos = await CompetitionDTOMapper.to_response_dtos(
        [escenario.competicion, otra], UserId(uuid4()), escenario.uow
    )

    assert len(lecturas) == 1
    assert [[c.name for c in d.golf_courses] for d in dtos] == [["Golf Meis"], [EL_PRAT.nombre]]
