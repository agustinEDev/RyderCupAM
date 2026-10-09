"""
La foto de cada jugador al generar sus partidas (#251, PR 4; D7 y D14 del 9 oct 2026).

Hándicap fijado al cerrar, barras de su inscripción con la regla de siempre,
hándicap de juego al 95 % con el tope de la competición (SCRATCH, 0) y los
golpes de cada hoyo con signo.

Campo de prueba: par 72, amarillas de hombre CR 71.2 / SR 128, dificultad = hoyo.

| Caso                                           | Resultado                                |
|------------------------------------------------|------------------------------------------|
| Fijado 10.0                                    | De juego 10, un golpe en los hoyos 1-10  |
| Plus -3.0                                      | De juego -4, da en los hoyos 15-18       |
| Tope 8, fijado 20.0                            | De juego 8                               |
| SCRATCH                                        | De juego 0, sin golpes; con su par       |
| Perfil distinto del fijado                     | Cuenta el fijado                         |
| Uno sin su color y otro sin género             | JugadoresSinBarraError con los dos       |
| Sin hándicap fijado                            | JugadoresSinHandicapError                |
"""

from datetime import date, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
    JugadoresSinBarraError,
    JugadoresSinHandicapError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_generation_block import (
    MISSING_GENDER,
    MISSING_HANDICAP,
    MISSING_TEE_COLOR,
)
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_user_repository import (
    InMemoryUserRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

VIERNES = date(2030, 10, 11)
PARES = [4, 3, 5, 4, 4, 3, 4, 5, 4, 4, 3, 5, 4, 4, 3, 4, 5, 4]


def _campo(barras=((TeeColor.YELLOW, Gender.MALE),)) -> MagicMock:
    """Como el de los tests de la Ryder: par 72, dificultad = número de hoyo."""
    tees = []
    for color, genero in barras:
        tee = MagicMock()
        tee.color = color
        tee.gender = genero
        tee.course_rating = Decimal("71.2")
        tee.slope_rating = 128
        tees.append(tee)
    hoyos = []
    for numero in range(1, 19):
        hoyo = MagicMock()
        hoyo.number = numero
        hoyo.par = PARES[numero - 1]
        hoyo.stroke_index = numero
        hoyos.append(hoyo)
    campo = MagicMock()
    campo.tees = tees
    campo.reference_card = hoyos
    return campo


class _Escenario:
    def __init__(self, play_mode=PlayMode.HANDICAP, tope=None, barras=None):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = InMemoryUserRepository()
        self.campos = AsyncMock()
        self.campos.find_by_id.return_value = _campo(barras or ((TeeColor.YELLOW, Gender.MALE),))
        self.competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=UserId(uuid4()),
            name=CompetitionName("Medal de octubre"),
            dates=DateRange(VIERNES, VIERNES),
            location=Location(CountryCode("ES")),
            play_mode=play_mode,
            tournament_type=TournamentType.STABLEFORD,
            status=CompetitionStatus.CLOSED,
            category_limits=[Decimal("12.0")],
            max_playing_handicap=tope,
        )
        self.franja = Round.create_franja(
            competition_id=self.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES,
            session_type=SessionType.MORNING,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 10, 4),
        )

    async def jugador(
        self,
        fijado: Decimal | None,
        genero: Gender | None = Gender.MALE,
        barras: TeeColor | None = None,
        nombre: str = "Ana",
    ) -> UserId:
        user = User.create(
            nombre, "Pérez", f"{uuid4().hex[:8]}@test.com", "P@ssw0rd123!", gender=genero
        )
        await self.usuarios.save(user)
        inscripcion = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=self.competicion.id,
            user_id=user.id,
            status=EnrollmentStatus.APPROVED,
            tee_color=barras,
        )
        inscripcion.congelar_handicap(fijado, 1 if fijado is not None else None)
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
        return user.id

    async def construir(self, user_ids):
        servicio = JugadoresDeLaPartida(self.campos, self.usuarios)
        return await servicio.construir(self.uow, self.competicion, self.franja, user_ids)


async def test_handicap_ten_plays_ten_with_a_stroke_on_holes_one_to_ten():
    escenario = _Escenario()
    ana = await escenario.jugador(Decimal("10.0"))

    jugador = (await escenario.construir([ana]))[ana]

    assert jugador.handicap == Decimal("10.0")
    assert jugador.playing_handicap == 10
    assert jugador.golpes_por_hoyo == (1,) * 10 + (0,) * 8
    assert (jugador.tee_color, jugador.tee_gender) == (TeeColor.YELLOW, Gender.MALE)


async def test_a_plus_player_gives_strokes_on_the_easiest_holes():
    escenario = _Escenario()
    ana = await escenario.jugador(Decimal("-3.0"))

    jugador = (await escenario.construir([ana]))[ana]

    assert jugador.playing_handicap == -4
    assert jugador.golpes_por_hoyo == (0,) * 14 + (-1,) * 4


async def test_the_competition_cap_applies():
    escenario = _Escenario(tope=8)
    ana = await escenario.jugador(Decimal("20.0"))

    assert (await escenario.construir([ana]))[ana].playing_handicap == 8


async def test_scratch_plays_zero_without_needing_rated_tees():
    """Sin golpes, pero con el par de cada hoyo para los puntos (P12)."""
    escenario = _Escenario(play_mode=PlayMode.SCRATCH)
    ana = await escenario.jugador(Decimal("20.0"), barras=TeeColor.RED)

    jugador = (await escenario.construir([ana]))[ana]

    assert jugador.playing_handicap == 0
    assert jugador.golpes_por_hoyo == (0,) * 18
    assert jugador.tee_color == TeeColor.RED
    assert jugador.par_por_hoyo == tuple(PARES)


async def test_the_snapshot_carries_the_par_of_each_hole():
    escenario = _Escenario()
    ana = await escenario.jugador(Decimal("10.0"))

    assert (await escenario.construir([ana]))[ana].par_por_hoyo == tuple(PARES)


async def test_the_fixed_handicap_counts_not_the_profile():
    """La foto es la del cierre: el perfil puede haber cambiado después (D14)."""
    escenario = _Escenario()
    ana = await escenario.jugador(Decimal("10.0"))
    perfil = await escenario.usuarios.find_by_id(ana)
    perfil.update_handicap(30.0)

    assert (await escenario.construir([ana]))[ana].handicap == Decimal("10.0")


async def test_everybody_without_tees_comes_in_one_error():
    escenario = _Escenario()
    rojas = await escenario.jugador(Decimal("10.0"), barras=TeeColor.RED, nombre="Bea")
    sin_genero = await escenario.jugador(Decimal("10.0"), genero=None, nombre="Carla")
    con_barras = await escenario.jugador(Decimal("10.0"))

    with pytest.raises(JugadoresSinBarraError) as error:
        await escenario.construir([rojas, sin_genero, con_barras])

    faltan = {(p.user_id, p.missing, p.tee_color) for p in error.value.players}
    assert faltan == {(rojas, MISSING_TEE_COLOR, "RED"), (sin_genero, MISSING_GENDER, None)}
    assert sorted(p.name for p in error.value.players) == ["Bea Pérez", "Carla Pérez"]


async def test_without_a_fixed_handicap_is_refused():
    escenario = _Escenario()
    sin = await escenario.jugador(None, nombre="Bea")
    con = await escenario.jugador(Decimal("10.0"))

    with pytest.raises(JugadoresSinHandicapError) as error:
        await escenario.construir([sin, con])

    assert [(p.user_id, p.missing) for p in error.value.players] == [(sin, MISSING_HANDICAP)]


class TestConOtroHandicap:
    """El fijado corregido tras el cierre (G1): mismas barras, otro hándicap de juego."""

    async def test_same_tees_new_playing_handicap(self):
        escenario = _Escenario()
        ana = await escenario.jugador(Decimal("10.0"))
        foto = (await escenario.construir([ana]))[ana]

        nueva = await JugadoresDeLaPartida(escenario.campos, escenario.usuarios).con_otro_handicap(
            escenario.competicion, escenario.franja, foto, Decimal("20.0")
        )

        assert (nueva.tee_color, nueva.tee_gender) == (foto.tee_color, foto.tee_gender)
        assert nueva.handicap == Decimal("20.0")
        assert nueva.playing_handicap == 21
        assert sum(nueva.golpes_por_hoyo) == 21

    async def test_scratch_keeps_zero(self):
        escenario = _Escenario(play_mode=PlayMode.SCRATCH)
        ana = await escenario.jugador(Decimal("10.0"))
        foto = (await escenario.construir([ana]))[ana]

        nueva = await JugadoresDeLaPartida(escenario.campos, escenario.usuarios).con_otro_handicap(
            escenario.competicion, escenario.franja, foto, Decimal("20.0")
        )

        assert (nueva.handicap, nueva.playing_handicap) == (Decimal("20.0"), 0)
        assert nueva.golpes_por_hoyo == (0,) * 18
