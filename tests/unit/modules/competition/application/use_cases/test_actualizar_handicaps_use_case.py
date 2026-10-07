"""
El botón «Actualizar hándicaps» del organizador (#251, decidido el 7 oct 2026).

| Caso                                                  | Resultado                                  |
|-------------------------------------------------------|--------------------------------------------|
| Stroke play cerrado, a tiempo                         | Una nueva (botón), lanzada tras guardar    |
| La última quedó incompleta                            | Se reanuda: solo lo que falta              |
| Hay una en curso                                      | 409: ya hay una                            |
| Fuera de la ventana (cerca de la salida)              | 400 con el motivo                          |
| Con una jornada en marcha                             | 400                                        |
| La zona del campo no se sabe                          | 400: no se sabe cuándo sale nadie          |
| Un jugador (no organiza)                              | 403                                        |
| Sin el refresco encendido (fuera de producción)       | 409                                        |
| Ryder cerrada                                         | Una nueva                                  |
| Tras iniciar, la RFEG da otro                         | Cambia el hándicap, no la categoría        |
| La ventana en la ficha                                | Abierta y hasta cuándo, o el motivo        |
"""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    ActualizacionEnCursoError,
    ActualizacionNoPermitidaError,
    NotCompetitionCreatorError,
    RefrescoDesactivadoError,
)
from src.modules.competition.application.services.handicaps_al_cerrar import HandicapsAlCerrar
from src.modules.competition.application.use_cases.actualizar_handicaps_use_case import (
    ActualizarHandicapsUseCase,
    VentanaDeActualizacionUseCase,
)
from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

VIERNES = date(2030, 10, 11)
# El viernes a las 9:00 en Madrid son las 7:00 UTC
A_TIEMPO = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)
CERCA = datetime(2030, 10, 11, 6, 59, tzinfo=UTC)
EN_MARCHA = datetime(2030, 10, 11, 12, 0, tzinfo=UTC)


class _Zonas:
    def __init__(self, zona="Europe/Madrid"):
        self.zona = zona

    async def for_course(self, _golf_course_id):
        return self.zona

    async def for_competition(self, _competition):
        return self.zona


class _Lanzador:
    def __init__(self, uow):
        self._uow = uow
        self.lanzadas = []

    def lanzar(self, update_id) -> None:
        self.lanzadas.append(update_id)


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())
        self.campo = GolfCourseId(uuid4())
        self.zonas = _Zonas()
        self.lanzador = _Lanzador(self.uow)

    async def torneo(self, tipo=TournamentType.STABLEFORD, status=CompetitionStatus.CLOSED):
        extra = (
            {"team_1_name": "Europa", "team_2_name": "América"}
            if tipo is TournamentType.RYDER_CUP
            else {}
        )
        self.competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=self.creador,
            name=CompetitionName("Medal de octubre"),
            dates=DateRange(VIERNES, VIERNES),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=tipo,
            status=status,
            **extra,
        )
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            if tipo is not TournamentType.RYDER_CUP:
                await self.uow.rounds.add(
                    Round.create_franja(
                        competition_id=self.competicion.id,
                        golf_course_id=self.campo,
                        round_date=VIERNES,
                        session_type=SessionType.MORNING,
                        hoja_de_salidas=HojaDeSalidas(time(9, 0), time(12, 0), 10, 4),
                    )
                )
            for _ in range(6):
                await self.uow.enrollments.add(
                    Enrollment.direct_enroll(
                        id=EnrollmentId.generate(),
                        competition_id=self.competicion.id,
                        user_id=UserId(uuid4()),
                    )
                )
        return self.competicion

    def caso(self, ahora=A_TIEMPO, lanzador=True):
        return ActualizarHandicapsUseCase(
            self.uow, self.zonas, self.lanzador if lanzador else None, reloj=lambda: ahora
        )

    async def pulsar(self, ahora=A_TIEMPO, quien=None, lanzador=True):
        return await self.caso(ahora, lanzador).execute(self.competicion.id, quien or self.creador)

    async def ultima(self):
        return await self.uow.handicap_updates.ultima_de(self.competicion.id)


@pytest.fixture
def e():
    return _Escenario()


class TestElBoton:
    async def test_a_tiempo_crea_una_y_la_lanza(self, e):
        await e.torneo()

        await e.pulsar()

        ultima = await e.ultima()
        assert ultima.origen is OrigenActualizacion.BOTON
        assert ultima.estado is EstadoActualizacion.EN_CURSO
        assert e.lanzador.lanzadas == [ultima.id]

    async def test_si_la_ultima_quedo_incompleta_la_reanuda(self, e):
        await e.torneo()
        incompleta = ActualizacionDeHandicaps.crear(
            e.competicion.id, OrigenActualizacion.CIERRE, A_TIEMPO
        )
        incompleta.terminar(pendientes=2, momento=A_TIEMPO)
        async with e.uow:
            await e.uow.handicap_updates.add(incompleta)

        await e.pulsar()

        ultima = await e.ultima()
        assert ultima.id == incompleta.id
        assert ultima.estado is EstadoActualizacion.EN_CURSO
        assert ultima.terminada is None
        assert e.lanzador.lanzadas == [incompleta.id]

    async def test_con_una_en_curso_409(self, e):
        await e.torneo()
        await e.pulsar()

        with pytest.raises(ActualizacionEnCursoError):
            await e.pulsar()

    async def test_cerca_de_la_salida_400_con_el_motivo(self, e):
        await e.torneo()

        with pytest.raises(ActualizacionNoPermitidaError, match="salida"):
            await e.pulsar(CERCA)

    async def test_con_la_jornada_en_marcha_400(self, e):
        await e.torneo(status=CompetitionStatus.IN_PROGRESS)

        with pytest.raises(ActualizacionNoPermitidaError, match="en marcha"):
            await e.pulsar(EN_MARCHA)

    async def test_sin_zona_del_campo_400(self, e):
        await e.torneo()
        e.zonas.zona = None

        with pytest.raises(ActualizacionNoPermitidaError, match="zona"):
            await e.pulsar()

    async def test_un_jugador_no(self, e):
        await e.torneo()

        with pytest.raises(NotCompetitionCreatorError):
            await e.pulsar(quien=UserId(uuid4()))

    async def test_sin_el_refresco_encendido_409(self, e):
        await e.torneo()

        with pytest.raises(RefrescoDesactivadoError):
            await e.pulsar(lanzador=False)

    async def test_en_una_ryder_cerrada_tambien(self, e):
        await e.torneo(TournamentType.RYDER_CUP)

        await e.pulsar()

        assert len(e.lanzador.lanzadas) == 1


class TestTrasIniciar:
    async def test_cambia_el_handicap_y_no_la_categoria(self, e):
        await e.torneo(status=CompetitionStatus.IN_PROGRESS)
        (inscripcion, *_) = await e.uow.enrollments.find_by_competition(e.competicion.id)
        inscripcion.congelar_handicap(Decimal("8.0"), 1)
        async with e.uow:
            await e.uow.enrollments.update(inscripcion)
        usuarios = SimpleNamespace()

        await HandicapsAlCerrar(e.uow, usuarios).corregir(
            e.competicion, inscripcion.user_id, Decimal("30.0")
        )

        guardada = await e.uow.enrollments.find_by_id(inscripcion.id)
        assert guardada.fixed_handicap == Decimal("30.0")
        assert guardada.fixed_category == 1


class TestLaVentanaEnLaFicha:
    async def test_abierta_y_hasta_cuando(self, e):
        await e.torneo()

        ventana = await VentanaDeActualizacionUseCase(e.uow, e.zonas, lambda: A_TIEMPO).execute(
            e.competicion.id, e.creador
        )

        # 9:00 en Madrid (7:00 UTC) menos 10 s por cada uno de los 6
        assert ventana.open
        assert ventana.closes_at == datetime(2030, 10, 11, 6, 59, tzinfo=UTC)
        assert ventana.reason is None

    async def test_cerrada_con_el_motivo(self, e):
        await e.torneo()

        ventana = await VentanaDeActualizacionUseCase(e.uow, e.zonas, lambda: CERCA).execute(
            e.competicion.id, e.creador
        )

        assert not ventana.open
        assert "salida" in ventana.reason

    async def test_a_un_jugador_nada(self, e):
        await e.torneo()

        ventana = await VentanaDeActualizacionUseCase(e.uow, e.zonas, lambda: A_TIEMPO).execute(
            e.competicion.id, UserId(uuid4())
        )

        assert ventana is None
