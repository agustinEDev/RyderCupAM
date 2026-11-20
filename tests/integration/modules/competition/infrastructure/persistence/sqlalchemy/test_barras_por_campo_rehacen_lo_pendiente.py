"""
Cambiar una barra por campo rehace lo pendiente en Postgres (barras por campo, 20 nov 2026).

Cubre lo que los tests unitarios no ven: la copia de trabajo de `LoPendiente`, su
recálculo y el guardado sobre las entidades bloqueadas con SQLAlchemy de verdad.
El campo y los usuarios son dobles (como en los unitarios); la competición, la
inscripción, el partido, la partida y los cambios, filas reales.

| Caso                                                      | Resultado                              |
|-----------------------------------------------------------|----------------------------------------|
| Su cambio propio a azules con un individual y una partida | Los dos, guardados con ella en azules  |
| pendientes en ese campo                                    | y el rival con su foto                 |
"""

from datetime import time
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.modules.competition.application.dto.enrollment_dto import (
    ChangeEnrollmentCourseTeeRequestDTO,
)
from src.modules.competition.application.use_cases.change_enrollment_course_tee_use_case import (
    ChangeEnrollmentCourseTeeUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    AHORA,
    BASE_DATE,
    jugadores,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _hoyos(par=4):
    hoyos = []
    for i in range(1, 19):
        hoyo = MagicMock()
        hoyo.number, hoyo.par, hoyo.stroke_index = i, par, i
        hoyos.append(hoyo)
    return hoyos


def _campo_doble():
    """Amarillas de hombre y azules de mujer, valoradas."""
    tees = []
    for color, sexo, slope in (
        (TeeColor.YELLOW, Gender.MALE, 128),
        (TeeColor.BLUE, Gender.FEMALE, 113),
    ):
        tee = MagicMock()
        tee.color, tee.gender = color, sexo
        tee.course_rating, tee.slope_rating, tee.par_total = Decimal("71.2"), slope, 72
        tee.holes = []
        tees.append(tee)
    campo = MagicMock()
    campo.name, campo.tees, campo.reference_card = "Campo real", tees, _hoyos()
    return campo


class _Campos:
    def __init__(self, campo_id, campo):
        self._campos = {campo_id: campo}

    async def find_by_id(self, golf_course_id):
        return self._campos.get(golf_course_id)


class _Usuarios:
    def __init__(self, generos):
        self._generos = generos

    def _usuario(self, user_id):
        usuario = MagicMock()
        usuario.id, usuario.gender = user_id, self._generos.get(user_id)
        return usuario

    async def find_by_id(self, user_id):
        return self._usuario(user_id)

    async def find_by_ids(self, user_ids):
        return [self._usuario(u) for u in user_ids]


async def _insert_course(db_session, creador) -> GolfCourseId:
    campo_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO golf_courses (id, name, country_code, course_type, creator_id, "
            "approval_status, physical_holes, is_pending_update, created_at, updated_at) "
            "VALUES (:id, :n, :c, :t, :cr, :s, :ph, false, :ca, :ua)"
        ),
        {
            "id": str(campo_id),
            "n": f"Campo {uuid4().hex[:6]}",
            "c": "ES",
            "t": "STANDARD_18",
            "cr": str(creador.value),
            "s": "APPROVED",
            "ph": 18,
            "ca": AHORA,
            "ua": AHORA,
        },
    )
    return GolfCourseId(campo_id)


async def test_su_cambio_propio_rehace_y_guarda_lo_pendiente(db_session, jugadores):  # noqa: F811
    """
    Given una competición con hándicap y un campo, la jugadora inscrita, un individual
        programado y una partida sin salir en ese campo, con ella en amarillas
    When fija azules como su cambio propio en ese campo
    Then el partido y la partida, leídos de nuevo de la base, la llevan en azules de
        mujer; el rival conserva su barra y su índice; y el cambio queda guardado
    """
    organizador, jugadora, rival, _ = jugadores
    campo = await _insert_course(db_session, organizador)
    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=organizador,
        name=CompetitionName(f"Barras por campo {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        team_1_name="A",
        team_2_name="B",
    )
    competicion.add_golf_course(campo, CountryCode("ES"))
    inscripcion = Enrollment.direct_enroll(
        id=EnrollmentId.generate(), competition_id=competicion.id, user_id=jugadora
    )
    ronda = Round.create(
        competition_id=competicion.id,
        golf_course_id=campo,
        round_date=BASE_DATE,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    franja = Round.create_franja(
        competition_id=competicion.id,
        golf_course_id=campo,
        round_date=BASE_DATE,
        session_type=SessionType.AFTERNOON,
        hoja_de_salidas=HojaDeSalidas(time(9, 0), time(11, 0), 10, 4),
    )

    def en_amarillas(user_id):
        return MatchPlayer.create(
            user_id=user_id,
            playing_handicap=10,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
            strokes_received=list(range(1, 11)),
            player_handicap=Decimal("18.0"),
        )

    partido = Match.create(
        round_id=ronda.id,
        match_number=1,
        team_a_players=[en_amarillas(jugadora)],
        team_b_players=[en_amarillas(rival)],
    )
    partida = Partida.crear(
        competicion.id,
        franja.id,
        1,
        [
            JugadorDePartida(
                user_id=jugadora,
                handicap=Decimal("18.0"),
                playing_handicap=10,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
                golpes_por_hoyo=(1,) * 10 + (0,) * 8,
                par_por_hoyo=(4,) * 18,
            )
        ],
    )
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    async with uow:
        await uow.competitions.add(competicion)
        await uow.enrollments.add(inscripcion)
        await uow.rounds.add(ronda)
        await uow.rounds.add(franja)
        await uow.matches.add(partido)
        await uow.partidas.anadir([partida])

    await ChangeEnrollmentCourseTeeUseCase(
        SQLAlchemyCompetitionUnitOfWork(db_session),
        golf_course_repository=_Campos(campo, _campo_doble()),
        user_repository=_Usuarios({jugadora: Gender.FEMALE, rival: Gender.MALE}),
    ).execute(
        ChangeEnrollmentCourseTeeRequestDTO(
            enrollment_id=inscripcion.id.value, golf_course_id=campo.value, tee_color=TeeColor.BLUE
        ),
        jugadora,
    )

    db_session.expire_all()
    leer = SQLAlchemyCompetitionUnitOfWork(db_session)
    guardado = await leer.matches.find_by_id(partido.id)
    ella = guardado.find_player(jugadora)
    assert (ella.tee_color, ella.tee_gender) == (TeeColor.BLUE, Gender.FEMALE)
    otro = guardado.find_player(rival)
    assert (otro.tee_color, otro.player_handicap) == (TeeColor.YELLOW, Decimal("18.0"))
    [suya] = (await leer.partidas.find_by_id(partida.id)).jugadores
    assert (suya.tee_color, suya.tee_gender) == (TeeColor.BLUE, Gender.FEMALE)
    cambios = await leer.barras_por_campo.del_campo(competicion.id, campo)
    assert cambios.propias == {jugadora: TeeColor.BLUE}
