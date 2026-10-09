"""
Generar las partidas de una franja (#251, PR 4; decidido el 6-9 oct 2026).

El organizador, del cierre a la primera salida: reparte a los jugadores con plaza
(y la inscripción aprobada) por hándicap fijado, en el orden que elija.

| Caso                                              | Resultado                                  |
|---------------------------------------------------|--------------------------------------------|
| 9 con plaza, de 4, más altos primero              | 4, 3, 2 a las 9:00, 9:10, 9:20; editable   |
| Más bajos primero                                 | Al revés                                   |
| Volver a generar                                  | Reemplaza las de antes                     |
| Retirado con plaza / de otra franja               | No entran                                  |
| Otro jugador / un admin                           | 403 / genera                               |
| Una sesión de Ryder                               | PartidasError                              |
| Inscripciones abiertas / a la 1.ª salida          | PlazoCerradoError                          |
| Alguna empezada                                   | PartidaEmpezadaError                       |
| Campo sin zona horaria                            | ZonaDesconocidaError (D10)                 |
| Uno solo                                          | RepartoImposibleError                      |
| Sin barras                                        | JugadoresSinBarraError, nada guardado      |
| Franja que no existe                              | RoundNotFoundError                         |
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.partidas_dto import GenerateTeeGroupsRequestDTO
from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    PartidasError,
    RoundNotFoundError,
)
from src.modules.competition.application.services.jornadas_de_la_competicion import (
    ZonaDesconocidaError,
)
from src.modules.competition.application.services.jugadores_de_la_partida import (
    JugadoresDeLaPartida,
    JugadoresSinBarraError,
)
from src.modules.competition.application.use_cases.partidas_use_case import (
    GenerarPartidasUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.partida import Partida, PartidaEmpezadaError
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.plazo_de_partidas import PlazoCerradoError
from src.modules.competition.domain.services.reparto_de_partidas import RepartoImposibleError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.estado_partida import EstadoPartida
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.orden_de_salida import OrdenDeSalida
from src.modules.competition.domain.value_objects.round_id import RoundId
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
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.services.test_jugadores_de_la_partida import (
    _campo,
)

pytestmark = pytest.mark.asyncio

VIERNES = date(2030, 10, 11)
# La víspera: las 9:00 de Madrid del viernes son las 7:00 UTC
JUEVES = datetime(2030, 10, 10, 12, 0, tzinfo=UTC)
A_LA_PRIMERA_SALIDA = datetime(2030, 10, 11, 7, 0, tzinfo=UTC)


class _Zonas:
    def __init__(self, zona: str | None = "Europe/Madrid"):
        self.zona = zona

    async def for_competition(self, _competition):
        return self.zona

    async def for_course(self, _golf_course_id):
        return self.zona


class _Escenario:
    def __init__(self, status=CompetitionStatus.CLOSED, zona="Europe/Madrid", ahora=JUEVES):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = InMemoryUserRepository()
        self.campos = AsyncMock()
        self.campos.find_by_id.return_value = _campo()
        self.creador = UserId(uuid4())
        self.competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=self.creador,
            name=CompetitionName("Medal de octubre"),
            dates=DateRange(VIERNES, VIERNES),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=TournamentType.STABLEFORD,
            status=status,
            category_limits=[Decimal("12.0")],
        )
        self.manana = self._franja(SessionType.MORNING, time(9, 0))
        self.tarde = self._franja(SessionType.AFTERNOON, time(15, 0))
        self.zonas = _Zonas(zona)
        self.ahora = ahora
        self._llegada = 0

    def _franja(self, sesion, primera):
        return Round.create_franja(
            competition_id=self.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES,
            session_type=sesion,
            hoja_de_salidas=HojaDeSalidas(primera, time(primera.hour + 1, 0), 10, 4),
        )

    async def guardar(self):
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            await self.uow.rounds.add(self.manana)
            await self.uow.rounds.add(self.tarde)

    async def con_plaza(
        self,
        fijado: str,
        franja=None,
        status=EnrollmentStatus.APPROVED,
        barras: TeeColor | None = None,
    ) -> UserId:
        user = User.create(
            "Jugador", fijado, f"{uuid4().hex[:8]}@test.com", "P@ssw0rd123!", gender=Gender.MALE
        )
        await self.usuarios.save(user)
        inscripcion = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=self.competicion.id,
            user_id=user.id,
            status=status,
            tee_color=barras,
        )
        inscripcion.congelar_handicap(Decimal(fijado), 1)
        self._llegada += 1
        async with self.uow:
            await self.uow.enrollments.add(inscripcion)
            await self.uow.plazas.add(
                PlazaEnFranja.crear(
                    self.competicion.id,
                    (franja or self.manana).id,
                    user.id,
                    datetime(2030, 10, 1, 10, self._llegada, tzinfo=UTC),
                )
            )
        return user.id

    def caso_de_uso(self) -> GenerarPartidasUseCase:
        return GenerarPartidasUseCase(
            uow=self.uow,
            jugadores=JugadoresDeLaPartida(self.campos, self.usuarios),
            zonas=self.zonas,
            user_repository=self.usuarios,
            reloj=lambda: self.ahora,
        )

    async def generar(
        self, orden=OrdenDeSalida.HIGH_FIRST, quien=None, is_admin=False, franja=None
    ):
        return await self.caso_de_uso().execute(
            (franja or self.manana).id.value,
            GenerateTeeGroupsRequestDTO(order=orden),
            quien or self.creador,
            is_admin,
        )


async def _con_nueve() -> tuple[_Escenario, list[UserId]]:
    escenario = _Escenario()
    await escenario.guardar()
    jugadores = [await escenario.con_plaza(f"{h}.0") for h in range(1, 10)]
    return escenario, jugadores


async def test_nine_of_four_highest_first():
    escenario, jugadores = await _con_nueve()

    vista = await escenario.generar()

    assert [len(g.players) for g in vista.groups] == [4, 3, 2]
    assert [g.number for g in vista.groups] == [1, 2, 3]
    assert [g.tee_time for g in vista.groups] == ["09:00", "09:10", "09:20"]
    assert [p.user_id for p in vista.groups[0].players] == [u.value for u in jugadores[8:4:-1]]
    assert vista.groups[0].players[0].name == "Jugador 9.0"
    assert vista.editable
    assert vista.unassigned_players == []
    assert len(await escenario.uow.partidas.de_la_franja(escenario.manana.id)) == 3


async def test_lowest_first():
    escenario, jugadores = await _con_nueve()

    vista = await escenario.generar(OrdenDeSalida.LOW_FIRST)

    assert [p.user_id for p in vista.groups[0].players] == [u.value for u in jugadores[:4]]


async def test_generating_again_replaces_the_previous_ones():
    escenario, _ = await _con_nueve()
    antes = await escenario.generar()

    despues = await escenario.generar(OrdenDeSalida.LOW_FIRST)

    guardadas = await escenario.uow.partidas.de_la_franja(escenario.manana.id)
    assert {p.id.value for p in guardadas} == {g.id for g in despues.groups}
    assert not {g.id for g in antes.groups} & {g.id for g in despues.groups}


async def test_only_approved_players_of_this_window():
    escenario = _Escenario()
    await escenario.guardar()
    dentro = [await escenario.con_plaza("5.0"), await escenario.con_plaza("6.0")]
    await escenario.con_plaza("7.0", status=EnrollmentStatus.WITHDRAWN)
    await escenario.con_plaza("8.0", franja=escenario.tarde)

    vista = await escenario.generar()

    assert {p.user_id for g in vista.groups for p in g.players} == {u.value for u in dentro}


async def test_only_the_organiser_or_an_admin():
    escenario, jugadores = await _con_nueve()

    with pytest.raises(NotCompetitionCreatorError):
        await escenario.generar(quien=jugadores[0])
    assert (await escenario.generar(quien=UserId(uuid4()), is_admin=True)).groups


async def test_a_ryder_session_has_no_groups():
    escenario = _Escenario()
    await escenario.guardar()
    sesion = Round.create(
        competition_id=escenario.competicion.id,
        golf_course_id=GolfCourseId.generate(),
        round_date=VIERNES,
        session_type=SessionType.EVENING,
        match_format=MatchFormat.SINGLES,
    )
    async with escenario.uow:
        await escenario.uow.rounds.add(sesion)

    with pytest.raises(PartidasError):
        await escenario.generar(franja=sesion)


@pytest.mark.parametrize(
    ("status", "ahora"),
    [
        pytest.param(CompetitionStatus.ACTIVE, JUEVES, id="inscripciones abiertas"),
        pytest.param(CompetitionStatus.IN_PROGRESS, A_LA_PRIMERA_SALIDA, id="a la primera salida"),
    ],
)
async def test_out_of_time(status, ahora):
    escenario = _Escenario(status=status, ahora=ahora)
    await escenario.guardar()
    await escenario.con_plaza("5.0")
    await escenario.con_plaza("6.0")

    with pytest.raises(PlazoCerradoError):
        await escenario.generar()


async def test_not_once_a_group_has_started():
    escenario, _ = await _con_nueve()
    vista = await escenario.generar()
    salida = await escenario.uow.partidas.find_by_id(
        next(p for p in await escenario.uow.partidas.de_la_franja(escenario.manana.id)).id
    )
    empezada = Partida(
        id=salida.id,
        competition_id=salida.competition_id,
        round_id=salida.round_id,
        numero=salida.numero,
        jugadores=salida.jugadores,
        marcadores=salida.marcadores,
        estado=EstadoPartida.IN_PROGRESS,
    )
    await escenario.uow.partidas.guardar([empezada])

    with pytest.raises(PartidaEmpezadaError):
        await escenario.generar()
    assert len(vista.groups) == 3


async def test_a_course_without_time_zone_cannot_generate():
    escenario = _Escenario(zona=None)
    await escenario.guardar()
    await escenario.con_plaza("5.0")
    await escenario.con_plaza("6.0")

    with pytest.raises(ZonaDesconocidaError):
        await escenario.generar()


async def test_one_player_alone_cannot_be_a_group():
    escenario = _Escenario()
    await escenario.guardar()
    await escenario.con_plaza("5.0")

    with pytest.raises(RepartoImposibleError):
        await escenario.generar()


async def test_players_without_tees_stop_it_and_nothing_is_saved():
    escenario = _Escenario()
    await escenario.guardar()
    await escenario.con_plaza("5.0")
    await escenario.con_plaza("6.0", barras=TeeColor.RED)

    with pytest.raises(JugadoresSinBarraError):
        await escenario.generar()
    assert await escenario.uow.partidas.de_la_franja(escenario.manana.id) == []


async def test_a_window_that_does_not_exist():
    escenario = _Escenario()
    await escenario.guardar()

    with pytest.raises(RoundNotFoundError):
        await escenario.caso_de_uso().execute(
            RoundId.generate().value,
            GenerateTeeGroupsRequestDTO(order=OrdenDeSalida.HIGH_FIRST),
            escenario.creador,
            False,
        )
