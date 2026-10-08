"""
Coger y soltar plaza en las franjas (#251, decidido el 6-8 oct 2026).

| Quién y cuándo                                       | Resultado                               |
|------------------------------------------------------|-----------------------------------------|
| El jugador, inscripciones abiertas                   | Coge plaza                              |
| El jugador, cambiándose (en lugar de)                | Cambia de golpe                         |
| El jugador, inscripciones cerradas                   | 400: hasta cerrar                       |
| El jugador, sin estar aprobado                       | 400                                     |
| Otro jugador por él                                  | 403                                     |
| El organizador, cerradas (antes de iniciar)          | Lo coloca                               |
| El organizador, en juego                             | 400                                     |
| La franja llena                                      | 400: «llena»                            |
| A la vez dos por la última plaza                     | Una sola (competición bloqueada)        |
| Soltar                                               | Ya no tiene plaza                       |
| Retirarse de la competición                          | Suelta todas sus plazas                 |
"""

from datetime import date, time
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import WithdrawEnrollmentRequestDTO
from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    PlazaEnFranjaError,
)
from src.modules.competition.application.use_cases.plazas_en_franjas_use_case import (
    CogerPlazaUseCase,
    SoltarPlazaUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
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


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())

    async def torneo(self, status=CompetitionStatus.ACTIVE, salidas_cupo=(time(9, 0), time(9, 10))):
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
        primera, ultima = salidas_cupo
        self.manana = self._franja(SessionType.MORNING, primera, ultima)
        self.tarde = self._franja(SessionType.AFTERNOON, time(15, 0), time(15, 10))
        async with self.uow:
            await self.uow.competitions.add(self.competicion)
            await self.uow.rounds.add(self.manana)
            await self.uow.rounds.add(self.tarde)

    def _franja(self, sesion, primera, ultima):
        return Round.create_franja(
            competition_id=self.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES,
            session_type=sesion,
            hoja_de_salidas=HojaDeSalidas(primera, ultima, 10, 3),
        )

    async def aprobado(self) -> UserId:
        user_id = UserId(uuid4())
        async with self.uow:
            await self.uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId.generate(), competition_id=self.competicion.id, user_id=user_id
                )
            )
        return user_id

    async def coger(self, franja, jugador, quien=None, en_lugar_de=None):
        await CogerPlazaUseCase(self.uow).execute(
            franja.id, jugador, quien or jugador, en_lugar_de=en_lugar_de
        )

    async def soltar(self, franja, jugador, quien=None):
        await SoltarPlazaUseCase(self.uow).execute(franja.id, jugador, quien or jugador)

    async def plazas(self):
        return {
            (p.round_id, p.user_id)
            for p in await self.uow.plazas.de_la_competicion(self.competicion.id)
        }


@pytest.fixture
def e():
    return _Escenario()


class TestElJugador:
    async def test_coge_plaza(self, e):
        await e.torneo()
        jugador = await e.aprobado()

        await e.coger(e.manana, jugador)

        assert await e.plazas() == {(e.manana.id, jugador)}

    async def test_se_cambia_de_golpe(self, e):
        await e.torneo()
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)

        await e.coger(e.tarde, jugador, en_lugar_de=e.manana.id)

        assert await e.plazas() == {(e.tarde.id, jugador)}

    async def test_con_las_inscripciones_cerradas_no(self, e):
        await e.torneo(status=CompetitionStatus.CLOSED)
        jugador = await e.aprobado()

        with pytest.raises(PlazaEnFranjaError, match="cerrar las inscripciones"):
            await e.coger(e.manana, jugador)

    async def test_sin_estar_aprobado_no(self, e):
        await e.torneo()

        with pytest.raises(PlazaEnFranjaError, match="inscrito"):
            await e.coger(e.manana, UserId(uuid4()))

    async def test_otro_jugador_por_el_no(self, e):
        await e.torneo()
        jugador = await e.aprobado()

        with pytest.raises(NotCompetitionCreatorError):
            await e.coger(e.manana, jugador, quien=UserId(uuid4()))

    async def test_la_franja_llena_no(self, e):
        await e.torneo(salidas_cupo=(time(9, 0), time(9, 0)))  # una salida de 3
        for _ in range(3):
            await e.coger(e.manana, await e.aprobado())

        with pytest.raises(PlazaEnFranjaError, match="llena"):
            await e.coger(e.manana, await e.aprobado())

    async def test_bloquea_la_competicion(self, e):
        """Dos a la vez por la última plaza: el segundo espera y ve que ya no hay."""
        await e.torneo()
        jugador = await e.aprobado()
        bloqueadas = []
        original = e.uow.competitions.find_by_id_for_update

        async def espia(competition_id):
            bloqueadas.append(competition_id)
            return await original(competition_id)

        e.uow.competitions.find_by_id_for_update = espia

        await e.coger(e.manana, jugador)

        assert bloqueadas == [e.competicion.id]

    async def test_suelta_su_plaza(self, e):
        await e.torneo()
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)

        await e.soltar(e.manana, jugador)

        assert await e.plazas() == set()


class TestElOrganizador:
    async def test_lo_coloca_con_las_inscripciones_cerradas(self, e):
        await e.torneo(status=CompetitionStatus.CLOSED)
        jugador = await e.aprobado()

        await e.coger(e.manana, jugador, quien=e.creador)

        assert await e.plazas() == {(e.manana.id, jugador)}

    async def test_tambien_se_mueve_a_si_mismo_con_las_inscripciones_cerradas(self, e):
        """El organizador también juega: sus reglas son las de organizador (revisión 3a)."""
        await e.torneo(status=CompetitionStatus.CLOSED)
        async with e.uow:
            await e.uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId.generate(),
                    competition_id=e.competicion.id,
                    user_id=e.creador,
                )
            )

        await e.coger(e.manana, e.creador, quien=e.creador)

        assert await e.plazas() == {(e.manana.id, e.creador)}

    async def test_en_juego_ya_no(self, e):
        await e.torneo(status=CompetitionStatus.IN_PROGRESS)
        jugador = await e.aprobado()

        with pytest.raises(PlazaEnFranjaError, match="iniciar"):
            await e.coger(e.manana, jugador, quien=e.creador)


class TestAlRetirarse:
    async def test_suelta_todas_sus_plazas(self, e):
        await e.torneo()
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)
        (inscripcion,) = [
            i
            for i in await e.uow.enrollments.find_by_competition(e.competicion.id)
            if i.user_id == jugador
        ]

        await WithdrawEnrollmentUseCase(e.uow).execute(
            WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), jugador
        )

        assert await e.plazas() == set()


class TestAlCerrarLasInscripciones:
    async def _cerrar(self, e):
        from src.modules.competition.application.dto.competition_dto import (
            CloseEnrollmentsRequestDTO,
        )
        from src.modules.competition.application.use_cases.close_enrollments_use_case import (
            CloseEnrollmentsUseCase,
        )
        from tests.unit.modules.competition.application.use_cases.helpers import (
            USUARIOS_CON_GENERO,
        )

        await CloseEnrollmentsUseCase(e.uow, USUARIOS_CON_GENERO).execute(
            CloseEnrollmentsRequestDTO(competition_id=e.competicion.id.value), e.creador
        )

    async def test_con_aprobados_sin_franja_no_se_cierra_y_dice_quienes(self, e):
        from src.modules.competition.application.services.franjas_al_cerrar import (
            PlayersWithoutTeeWindowError,
        )

        await e.torneo()
        con = await e.aprobado()
        sin = await e.aprobado()
        await e.coger(e.manana, con)

        with pytest.raises(PlayersWithoutTeeWindowError) as error:
            await self._cerrar(e)

        assert [p.user_id for p in error.value.players] == [sin]
        assert error.value.players[0].missing == "TEE_WINDOW"
        competicion = await e.uow.competitions.find_by_id(e.competicion.id)
        assert competicion.status is CompetitionStatus.ACTIVE

    async def test_con_todos_en_su_franja_se_cierra(self, e):
        await e.torneo()
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)

        await self._cerrar(e)

        competicion = await e.uow.competitions.find_by_id(e.competicion.id)
        assert competicion.status is CompetitionStatus.CLOSED


class TestElCalendario:
    async def test_cada_franja_dice_cuantas_quedan_y_quien_va(self, e):
        from src.modules.competition.application.dto.round_match_dto import GetScheduleRequestDTO
        from src.modules.competition.application.use_cases.get_schedule_use_case import (
            GetScheduleUseCase,
        )

        await e.torneo()
        a, b = await e.aprobado(), await e.aprobado()
        await e.coger(e.manana, a)
        await e.coger(e.manana, b)

        calendario = await GetScheduleUseCase(e.uow).execute(
            GetScheduleRequestDTO(competition_id=e.competicion.id.value)
        )

        por_id = {r.id: r for r in calendario.days[0].rounds}
        manana = por_id[e.manana.id.value].tee_sheet
        tarde = por_id[e.tarde.id.value].tee_sheet
        assert (manana.capacity, manana.places_taken) == (6, 2)
        assert manana.player_ids == [a.value, b.value]
        assert (tarde.places_taken, tarde.player_ids) == (0, [])


class TestNadiePierdeSuSitio:
    """
    Cambiar la forma en cualquier dirección mientras nadie de dentro pierda su
    sitio, franja a franja (decisión 5 de la #251).
    """

    async def _llena_de(self, e, n):
        jugadores = [await e.aprobado() for _ in range(n)]
        for j in jugadores:
            await e.coger(e.manana, j)
        return jugadores

    async def test_achicarla_por_debajo_de_los_que_hay_no(self, e):
        from src.modules.competition.application.dto.round_match_dto import (
            TeeSheetDTO,
            UpdateRoundRequestDTO,
        )
        from src.modules.competition.application.exceptions import FranjaInvalidaError
        from src.modules.competition.application.use_cases.update_round_use_case import (
            UpdateRoundUseCase,
        )

        await e.torneo()
        await self._llena_de(e, 4)
        una_salida = TeeSheetDTO(
            first_tee_time=time(9, 0), last_tee_time=time(9, 0), interval_minutes=10, group_size=3
        )

        with pytest.raises(FranjaInvalidaError, match="4"):
            await UpdateRoundUseCase(e.uow).execute(
                UpdateRoundRequestDTO(round_id=e.manana.id.value, tee_sheet=una_salida), e.creador
            )

    async def test_achicarla_sin_dejar_a_nadie_fuera_si(self, e):
        from src.modules.competition.application.dto.round_match_dto import (
            TeeSheetDTO,
            UpdateRoundRequestDTO,
        )
        from src.modules.competition.application.use_cases.update_round_use_case import (
            UpdateRoundUseCase,
        )

        await e.torneo()
        await self._llena_de(e, 3)
        una_salida = TeeSheetDTO(
            first_tee_time=time(9, 0), last_tee_time=time(9, 0), interval_minutes=10, group_size=3
        )

        await UpdateRoundUseCase(e.uow).execute(
            UpdateRoundRequestDTO(round_id=e.manana.id.value, tee_sheet=una_salida), e.creador
        )

    async def test_borrarla_con_gente_dentro_no(self, e):
        from src.modules.competition.application.dto.round_match_dto import DeleteRoundRequestDTO
        from src.modules.competition.application.exceptions import FranjaInvalidaError
        from src.modules.competition.application.use_cases.delete_round_use_case import (
            DeleteRoundUseCase,
        )

        await e.torneo()
        await self._llena_de(e, 1)

        with pytest.raises(FranjaInvalidaError, match="plaza"):
            await DeleteRoundUseCase(e.uow).execute(
                DeleteRoundRequestDTO(round_id=e.manana.id.value), e.creador
            )

    async def test_moverla_a_un_dia_en_que_alguno_ya_juega_no(self, e):
        from datetime import timedelta

        from src.modules.competition.application.dto.round_match_dto import UpdateRoundRequestDTO
        from src.modules.competition.application.exceptions import FranjaInvalidaError
        from src.modules.competition.application.use_cases.update_round_use_case import (
            UpdateRoundUseCase,
        )

        await e.torneo()
        e.competicion._dates = DateRange(VIERNES, VIERNES + timedelta(days=1))
        sabado = Round.create_franja(
            competition_id=e.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES + timedelta(days=1),
            session_type=SessionType.EVENING,
            hoja_de_salidas=HojaDeSalidas(time(18, 0), time(18, 10), 10, 3),
        )
        async with e.uow:
            await e.uow.competitions.update(e.competicion)
            await e.uow.rounds.add(sabado)
        jugador = await e.aprobado()
        e.competicion.update_stroke_play(max_matchdays_per_player=2)
        async with e.uow:
            await e.uow.competitions.update(e.competicion)
        await e.coger(e.manana, jugador)
        await e.coger(sabado, jugador)

        with pytest.raises(FranjaInvalidaError, match="ya juega"):
            await UpdateRoundUseCase(e.uow).execute(
                UpdateRoundRequestDTO(round_id=sabado.id.value, round_date=VIERNES), e.creador
            )

    async def test_bajar_el_cupo_de_jornadas_por_debajo_de_alguno_no(self, e):
        from datetime import timedelta

        from src.modules.competition.application.dto.competition_dto import (
            StrokePlaySettingsDTO,
        )
        from src.modules.competition.application.use_cases.update_stroke_play_settings_use_case import (
            UpdateStrokePlaySettingsUseCase,
        )
        from src.modules.competition.domain.value_objects.stroke_play_setup import (
            StrokePlaySettingsError,
        )

        await e.torneo()
        e.competicion._dates = DateRange(VIERNES, VIERNES + timedelta(days=1))
        e.competicion.update_stroke_play(max_matchdays_per_player=2)
        sabado = Round.create_franja(
            competition_id=e.competicion.id,
            golf_course_id=GolfCourseId.generate(),
            round_date=VIERNES + timedelta(days=1),
            session_type=SessionType.MORNING,
            hoja_de_salidas=HojaDeSalidas(time(9, 0), time(9, 10), 10, 3),
        )
        async with e.uow:
            await e.uow.competitions.update(e.competicion)
            await e.uow.rounds.add(sabado)
        jugador = await e.aprobado()
        await e.coger(e.manana, jugador)
        await e.coger(sabado, jugador)

        with pytest.raises(StrokePlaySettingsError, match="2 jornadas"):
            await UpdateStrokePlaySettingsUseCase(e.uow).execute(
                e.competicion.id.value,
                StrokePlaySettingsDTO(max_matchdays_per_player=1),
                e.creador,
            )
