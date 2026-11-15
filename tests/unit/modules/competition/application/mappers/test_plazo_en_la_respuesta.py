"""
El plazo de inscripción en la respuesta de cada competición (16 nov 2026), para la app.

| Campo                          | Caso                                             | Valor                       |
|--------------------------------|--------------------------------------------------|-----------------------------|
| enrollment_deadline            | campo en Canarias                                | 12:00 del día antes, +00:00 |
| enrollment_deadline            | dos campos                                       | la zona del primero         |
| enrollment_deadline            | sin campo                                        | 12:00 de Madrid, con desfase|
| enrollment_deadline            | serializado                                      | ISO con su desfase          |
| enrollment_deadline_applies    | abierta antes del plazo                          | true                        |
| enrollment_deadline_applies    | reabierta a mano pasado el plazo (exenta)        | false                       |
| enrollment_deadline_applies    | cerrada otra vez a mano (la excepción acabó)     | true                        |
| enrollment_deadline_applies    | en borrador                                      | true                        |
| enrollment_closed_by_deadline  | cerrada por el plazo / a mano                    | true / false                |
| listado                        | varias competiciones                             | los campos en UNA lectura,  |
|                                |                                                  | sin pedir zonas aparte      |
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.application.mappers.competition_mapper import CompetitionDTOMapper
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.campo_de_la_competicion import (
    CampoDeLaCompeticion,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

TORNEO = date(2026, 11, 20)
ANTES = datetime(2026, 11, 10, tzinfo=UTC)
DESPUES = datetime(2026, 11, 19, 13, 0, tzinfo=UTC)
CANARIAS = CampoDeLaCompeticion(
    GolfCourseId.generate(), "Maspalomas", CountryCode("ES"), zona="Atlantic/Canary"
)


async def _con(uow, abierta: datetime | None = ANTES, campos=()) -> Competition:
    competition = Competition.create(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName("Copa del plazo"),
        dates=DateRange(TORNEO, TORNEO + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        team_1_name="A",
        team_2_name="B",
        play_mode=PlayMode.SCRATCH,
        enrollment_opens_days_before=None if abierta else 5,
    )
    if abierta is not None:
        competition.activate(now=abierta)
    async with uow:
        await uow.competitions.add(competition)
    if campos:
        uow.competitions.con_campos(competition.id, list(campos))
    return competition


async def _dto(uow, competition):
    return await CompetitionDTOMapper.to_response_dto(competition, competition.creator_id, uow)


class TestElPlazo:
    async def test_en_la_zona_del_primer_campo(self):
        """Given un campo en Canarias / Then las 12:00 de Canarias del día antes, +00:00."""
        uow = InMemoryUnitOfWork()
        competition = await _con(uow, campos=[CANARIAS])

        dto = await _dto(uow, competition)

        assert dto.enrollment_deadline == datetime(
            2026, 11, 19, 12, 0, tzinfo=ZoneInfo("Atlantic/Canary")
        )
        assert dto.enrollment_deadline.utcoffset() == timedelta(0)

    async def test_con_dos_campos_manda_el_primero(self):
        """Given Canarias primero y luego un campo de Madrid / Then la de Canarias."""
        uow = InMemoryUnitOfWork()
        madrid = CampoDeLaCompeticion(
            GolfCourseId.generate(), "El Prat", CountryCode("ES"), zona="Europe/Madrid"
        )
        competition = await _con(uow, campos=[CANARIAS, madrid])

        dto = await _dto(uow, competition)

        assert dto.enrollment_deadline.utcoffset() == timedelta(0)

    async def test_sin_campo_la_de_madrid_con_su_desfase(self):
        """Given sin campos / Then las 12:00 de Madrid; serializado con +01:00."""
        uow = InMemoryUnitOfWork()
        competition = await _con(uow)

        dto = await _dto(uow, competition)

        assert dto.enrollment_deadline.utcoffset() == timedelta(hours=1)
        assert dto.model_dump(mode="json")["enrollment_deadline"] == "2026-11-19T12:00:00+01:00"


class TestSiLeAplica:
    async def test_abierta_antes_del_plazo_si(self):
        """Given abierta antes del plazo / Then le aplica."""
        uow = InMemoryUnitOfWork()

        dto = await _dto(uow, await _con(uow))

        assert dto.enrollment_deadline_applies is True
        assert dto.enrollment_closed_by_deadline is False

    async def test_reabierta_a_mano_pasado_el_plazo_no(self):
        """Given reabierta a mano pasado el plazo / Then exenta: no le aplica."""
        uow = InMemoryUnitOfWork()
        competition = await _con(uow)
        competition.close_enrollments()
        competition.reopen_enrollments(now=DESPUES)

        assert (await _dto(uow, competition)).enrollment_deadline_applies is False

    async def test_cerrada_otra_vez_a_mano_si(self):
        """Given reabierta tarde y cerrada otra vez a mano / Then la excepción acabó."""
        uow = InMemoryUnitOfWork()
        competition = await _con(uow)
        competition.close_enrollments()
        competition.reopen_enrollments(now=DESPUES)
        competition.close_enrollments()

        assert (await _dto(uow, competition)).enrollment_deadline_applies is True

    async def test_en_borrador_si(self):
        """Given en borrador (apertura programada) / Then le aplica."""
        uow = InMemoryUnitOfWork()

        assert (await _dto(uow, await _con(uow, abierta=None))).enrollment_deadline_applies is True

    async def test_la_exenta_con_su_campo_de_canarias(self):
        """Given reabierta a las 11:30 UTC (12:00 Madrid ya, 11:30 Canarias aún no) / Then aplica."""
        uow = InMemoryUnitOfWork()
        competition = await _con(uow, campos=[CANARIAS])
        competition.close_enrollments()
        competition.reopen_enrollments(now=datetime(2026, 11, 19, 11, 30, tzinfo=UTC))

        assert (await _dto(uow, competition)).enrollment_deadline_applies is True


class TestQuienLaCerro:
    @pytest.mark.parametrize("por_el_plazo", [True, False])
    async def test_cerrada_por_el_plazo_o_a_mano(self, por_el_plazo):
        """Given cerrada por el plazo (o a mano) / Then lo dice."""
        uow = InMemoryUnitOfWork()
        competition = await _con(uow)
        competition.close_enrollments(by_deadline=por_el_plazo)

        assert (await _dto(uow, competition)).enrollment_closed_by_deadline is por_el_plazo


class TestUnListado:
    async def test_las_zonas_salen_de_la_misma_lectura_de_campos(self):
        """
        Given tres competiciones, una en Canarias
        When se listan
        Then una sola lectura de campos para todas, y cada una con su plazo
        """
        uow = InMemoryUnitOfWork()
        canaria = await _con(uow, campos=[CANARIAS])
        otras = [await _con(uow), await _con(uow)]
        lecturas = []
        original = uow.competitions.campos_de

        async def cuenta(ids):
            lecturas.append(list(ids))
            return await original(ids)

        uow.competitions.campos_de = cuenta

        dtos = await CompetitionDTOMapper.to_response_dtos(
            [canaria, *otras], canaria.creator_id, uow
        )

        assert len(lecturas) == 1
        assert dtos[0].enrollment_deadline.utcoffset() == timedelta(0)
        assert all(d.enrollment_deadline.utcoffset() == timedelta(hours=1) for d in dtos[1:])
