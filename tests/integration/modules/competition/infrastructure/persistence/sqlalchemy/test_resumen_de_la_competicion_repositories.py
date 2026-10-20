"""
Las lecturas del resumen de «Mis competiciones» contra PostgreSQL (FE #846).

| Caso                                              | Resultado                               |
|---------------------------------------------------|-----------------------------------------|
| Dos competiciones, una con dos campos             | Cada una los suyos, en su orden         |
| Una competición sin campos                        | No aparece                              |
| Sin competiciones                                 | {} sin consultar                        |
| Partidos de un jugador en varias rondas           | Los suyos (equipo A o B), de esas rondas |
| Sin rondas                                        | [] sin consultar                        |
| Solo las competiciones pedidas                    | Las demás no aparecen                   |
| Las plazas de un jugador                          | Las suyas, no las de otro               |
"""

from datetime import UTC, datetime, time
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.match_repository import (
    SQLAlchemyMatchRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.plaza_en_franja_repository import (
    SQLAlchemyPlazaEnFranjaRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_player_history import (
    BASE_DATE,
    _create_competition,
    _create_match,
    _create_round,
)

# Los fixtures `golf_course_id`, `player_id` y `rival_id`, de ese mismo fichero
pytest_plugins = [
    "tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_player_history"
]

pytestmark = [pytest.mark.integration]


async def _campo(db_session, creador, nombre: str, pais: str = "ES") -> GolfCourse:
    campo = GolfCourse.create(
        name=f"{nombre} {uuid4().hex[:6]}",
        country_code=CountryCode(pais),
        course_type=CourseType.STANDARD_18,
        creator_id=creador,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    campo.approve()
    await GolfCourseRepository(db_session).save(campo)
    await db_session.commit()
    return campo


async def _competicion_con(
    db_session, creador, campos: list[GolfCourse], orden: list[GolfCourse] | None = None
) -> Competition:
    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creador,
        name=CompetitionName(f"Resumen {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE),
        location=Location(main_country=CountryCode("ES"), adjacent_country_1=CountryCode("PT")),
        play_mode=PlayMode.HANDICAP,
        team_1_name="A",
        team_2_name="B",
    )
    for campo in campos:
        competicion.add_golf_course(campo.id, campo.country_code)
    # Otro orden que el de llegada: el que manda es `display_order`
    if orden:
        competicion.reorder_golf_courses([(c.id, i) for i, c in enumerate(orden, start=1)])
    await SQLAlchemyCompetitionRepository(db_session).add(competicion)
    await db_session.commit()
    return competicion


async def test_each_competition_gets_its_courses_in_order(db_session, player_id):
    meis = await _campo(db_session, player_id, "Golf Meis")
    prat = await _campo(db_session, player_id, "El Prat")
    lisboa = await _campo(db_session, player_id, "Lisboa", "PT")
    dos = await _competicion_con(db_session, player_id, [meis, prat], orden=[prat, meis])
    una = await _competicion_con(db_session, player_id, [lisboa])
    ninguna = await _competicion_con(db_session, player_id, [])

    campos = await SQLAlchemyCompetitionRepository(db_session).campos_de(
        [dos.id, una.id, ninguna.id]
    )

    assert [(c.golf_course_id, c.nombre) for c in campos[dos.id]] == [
        (prat.id, prat.name),
        (meis.id, meis.name),
    ]
    assert [(c.golf_course_id, c.country_code) for c in campos[una.id]] == [
        (lisboa.id, CountryCode("PT"))
    ]
    assert ninguna.id not in campos


async def test_only_the_competitions_asked_for(db_session, player_id):
    meis = await _campo(db_session, player_id, "Golf Meis")
    pedida = await _competicion_con(db_session, player_id, [meis])
    await _competicion_con(db_session, player_id, [meis])

    campos = await SQLAlchemyCompetitionRepository(db_session).campos_de([pedida.id])

    assert list(campos) == [pedida.id]


async def test_the_places_of_one_player(db_session, player_id, rival_id, golf_course_id):
    competicion = await _create_competition(db_session, player_id)
    franjas = []
    for sesion in (SessionType.MORNING, SessionType.AFTERNOON):
        franja = Round.create_franja(
            competition_id=competicion.id,
            golf_course_id=golf_course_id,
            round_date=BASE_DATE,
            session_type=sesion,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 10, 4),
        )
        await SQLAlchemyRoundRepository(db_session).add(franja)
        franjas.append(franja)
    await db_session.commit()
    plazas = SQLAlchemyPlazaEnFranjaRepository(db_session)
    ahora = datetime(2026, 5, 1, tzinfo=UTC)
    await plazas.add(PlazaEnFranja.crear(competicion.id, franjas[0].id, player_id, ahora))
    await plazas.add(PlazaEnFranja.crear(competicion.id, franjas[1].id, rival_id, ahora))
    await db_session.commit()

    mias = await plazas.del_jugador(competicion.id, player_id)

    assert [(p.round_id, p.user_id) for p in mias] == [(franjas[0].id, player_id)]


async def test_without_competitions_nothing(db_session):
    assert await SQLAlchemyCompetitionRepository(db_session).campos_de([]) == {}


async def test_the_matches_of_a_player_in_several_rounds(
    db_session, player_id, rival_id, golf_course_id
):
    competicion = await _create_competition(db_session, player_id)
    primera = await _create_round(db_session, competicion, golf_course_id, BASE_DATE)
    segunda = await _create_round(db_session, competicion, golf_course_id, BASE_DATE)
    fuera = await _create_round(db_session, competicion, golf_course_id, BASE_DATE)
    en_a = await _create_match(db_session, primera, [player_id], [rival_id], completed=False)
    en_b = await _create_match(db_session, segunda, [rival_id], [player_id], completed=False)
    await _create_match(db_session, segunda, [rival_id], [rival_id], match_number=2)
    await _create_match(db_session, fuera, [player_id], [rival_id], completed=False)

    partidos = await SQLAlchemyMatchRepository(db_session).find_by_rounds_for_player(
        [primera.id, segunda.id], player_id
    )

    assert {p.id for p in partidos} == {en_a.id, en_b.id}


async def test_without_rounds_no_matches(db_session, player_id):
    assert (
        await SQLAlchemyMatchRepository(db_session).find_by_rounds_for_player([], player_id) == []
    )
