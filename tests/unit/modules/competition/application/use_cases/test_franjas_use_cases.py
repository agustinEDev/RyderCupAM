"""
Las franjas de un Stableford o un Medal: crear, cambiar, borrar y verlas (#251).

Decidido con Agustín el 6-7 oct 2026. Una franja es la sesión con su hoja de
salidas; el cupo sale de ella. Mañana/Tarde/Noche, hasta 3 por jornada, sin
solaparse, y se tocan hasta iniciar la competición.

| Caso                                               | Resultado                          |
|----------------------------------------------------|------------------------------------|
| Crear una franja con su hoja                       | Individual al 95 %, con su hoja    |
| Crear en stroke play sin hoja                      | 400                                |
| Crear en stroke play con formato de partido        | 400: la franja no lleva formato    |
| Crear en una Ryder con hoja                        | 400                                |
| Crear una Ryder sin formato                        | 400                                |
| Crear una Ryder con allowance pero sin formato     | 400 (antes 500)                    |
| Moverla a otro campo donde choca                   | 400                                |
| Crear solapada con otra de la jornada              | 400, diciendo con cuál             |
| Crear con hoja imposible (intervalo 30)            | 400                                |
| Crear en stroke play en juego                      | 400: hasta iniciar                 |
| Cambiar la hoja                                    | Se cambia                          |
| Cambiar a una hora que choca                       | 400                                |
| Moverla a otro día donde choca                     | 400                                |
| Cambiar el formato de una franja                   | 400                                |
| Borrar en stroke play en juego                     | 400                                |
| La agenda automática en un stroke play             | 400: es de la Ryder                |
| La agenda en modo manual en un stroke play         | Vale (solo «créalas una a una»)    |
| La agenda en un stroke play en juego               | 400: hasta iniciar                 |
| El calendario                                      | Cada franja con su hoja, horas y cupo, y el cupo total |
"""

from datetime import date, time
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    ConfigureScheduleRequestDTO,
    CreateRoundRequestDTO,
    DeleteRoundRequestDTO,
    GetScheduleRequestDTO,
    TeeSheetDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.exceptions import (
    AgendaNotEditableError,
    FranjaInvalidaError,
)
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    ConfigureScheduleUseCase,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CreateRoundUseCase,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
)
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.schedule_config_mode import (
    ScheduleConfigMode,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

SABADO = date(2030, 10, 12)
DOMINGO = date(2030, 10, 13)


def _hoja(primera="09:00", ultima="12:00", intervalo=10, partida=4) -> TeeSheetDTO:
    return TeeSheetDTO(
        first_tee_time=time.fromisoformat(primera),
        last_tee_time=time.fromisoformat(ultima),
        interval_minutes=intervalo,
        group_size=partida,
    )


class _Escenario:
    def __init__(self):
        self.uow = InMemoryUnitOfWork()
        self.creador = UserId(uuid4())
        self.campo = GolfCourseId(uuid4())

    async def torneo(
        self, tipo=TournamentType.STABLEFORD, status=CompetitionStatus.ACTIVE
    ) -> Competition:
        extra = (
            {"team_1_name": "Europa", "team_2_name": "América"}
            if tipo is TournamentType.RYDER_CUP
            else {}
        )
        competicion = Competition(
            id=CompetitionId(uuid4()),
            creator_id=self.creador,
            name=CompetitionName("Medal de octubre"),
            dates=DateRange(SABADO, DOMINGO),
            location=Location(CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
            tournament_type=tipo,
            status=status,
            max_players=100,
            **extra,
        )
        competicion._golf_courses.append(
            CompetitionGolfCourse.create(
                competition_id=competicion.id, golf_course_id=self.campo, display_order=1
            )
        )
        async with self.uow:
            await self.uow.competitions.add(competicion)
        self.competicion = competicion
        return competicion

    async def crear(self, hoja=None, sesion="MORNING", dia=SABADO, formato=None, campo=None):
        return await CreateRoundUseCase(self.uow).execute(
            CreateRoundRequestDTO(
                competition_id=self.competicion.id.value,
                golf_course_id=(campo or self.campo).value,
                round_date=dia,
                session_type=sesion,
                match_format=formato,
                tee_sheet=hoja,
            ),
            self.creador,
        )

    async def cambiar(self, round_id, **campos):
        return await UpdateRoundUseCase(self.uow).execute(
            UpdateRoundRequestDTO(round_id=round_id, **campos), self.creador
        )

    async def sesion(self, round_id):
        from src.modules.competition.domain.value_objects.round_id import RoundId

        return await self.uow.rounds.find_by_id(RoundId(round_id))

    async def poner_estado(self, status):
        self.competicion._status = status
        async with self.uow:
            await self.uow.competitions.update(self.competicion)


@pytest.fixture
def e():
    return _Escenario()


class TestCrear:
    async def test_una_franja_con_su_hoja(self, e):
        await e.torneo()

        creada = await e.crear(_hoja("09:00", "12:00"))

        franja = await e.sesion(creada.id)
        assert franja.hoja_de_salidas == HojaDeSalidas(time(9, 0), time(12, 0), 10, 4)
        assert franja.match_format.value == "SINGLES"
        assert franja.allowance_percentage == 95

    async def test_en_stroke_play_sin_hoja_no(self, e):
        await e.torneo()

        with pytest.raises(FranjaInvalidaError, match="hoja de salidas"):
            await e.crear()

    async def test_en_stroke_play_con_formato_no(self, e):
        await e.torneo()

        with pytest.raises(FranjaInvalidaError, match="formato"):
            await e.crear(_hoja(), formato="FOURBALL")

    async def test_en_una_ryder_con_hoja_no(self, e):
        await e.torneo(TournamentType.RYDER_CUP)

        with pytest.raises(FranjaInvalidaError, match="Ryder"):
            await e.crear(_hoja(), formato="SINGLES")

    async def test_en_una_ryder_con_allowance_y_sin_formato_no(self, e):
        """Antes acababa en un 500: el allowance contaba como si trajera formato."""
        await e.torneo(TournamentType.RYDER_CUP)

        with pytest.raises(FranjaInvalidaError, match="formato"):
            await CreateRoundUseCase(e.uow).execute(
                CreateRoundRequestDTO(
                    competition_id=e.competicion.id.value,
                    golf_course_id=e.campo.value,
                    round_date=SABADO,
                    session_type="MORNING",
                    allowance_percentage=80,
                ),
                e.creador,
            )

    async def test_en_una_ryder_sin_formato_no(self, e):
        await e.torneo(TournamentType.RYDER_CUP)

        with pytest.raises(FranjaInvalidaError, match="formato"):
            await e.crear()

    async def test_solapada_con_otra_de_la_jornada_no(self, e):
        await e.torneo()
        await e.crear(_hoja("09:00", "12:00"))

        with pytest.raises(FranjaInvalidaError, match="MORNING"):
            await e.crear(_hoja("11:00", "14:00"), sesion="AFTERNOON")

    async def test_otra_jornada_a_la_misma_hora_si(self, e):
        await e.torneo()
        await e.crear(_hoja("09:00", "12:00"))

        await e.crear(_hoja("09:00", "12:00"), dia=DOMINGO)

    async def test_con_una_hoja_imposible_no(self, e):
        await e.torneo()

        with pytest.raises(FranjaInvalidaError, match="5 y 20"):
            await e.crear(_hoja(intervalo=30))

    async def test_en_juego_ya_no(self, e):
        await e.torneo(status=CompetitionStatus.IN_PROGRESS)

        with pytest.raises(AgendaNotEditableError, match="iniciar"):
            await e.crear(_hoja())


class TestCambiar:
    async def test_cambia_la_hoja(self, e):
        await e.torneo()
        creada = await e.crear(_hoja("09:00", "12:00"))

        await e.cambiar(creada.id, tee_sheet=_hoja("09:30", "12:30", partida=3))

        franja = await e.sesion(creada.id)
        assert franja.hoja_de_salidas == HojaDeSalidas(time(9, 30), time(12, 30), 10, 3)

    async def test_a_una_hora_que_choca_no(self, e):
        await e.torneo()
        await e.crear(_hoja("09:00", "12:00"))
        tarde = await e.crear(_hoja("15:00", "18:00"), sesion="AFTERNOON")

        with pytest.raises(FranjaInvalidaError, match="MORNING"):
            await e.cambiar(tarde.id, tee_sheet=_hoja("11:00", "14:00"))

    async def test_moverla_a_otro_dia_donde_choca_no(self, e):
        await e.torneo()
        await e.crear(_hoja("09:00", "12:00"), dia=DOMINGO)
        tarde = await e.crear(_hoja("10:00", "13:00"), sesion="AFTERNOON")

        with pytest.raises(FranjaInvalidaError, match="MORNING"):
            await e.cambiar(tarde.id, round_date=DOMINGO)

    async def test_moverla_a_otro_campo_donde_choca_no(self, e):
        await e.torneo()
        otro = GolfCourseId(uuid4())
        e.competicion._golf_courses.append(
            CompetitionGolfCourse.create(
                competition_id=e.competicion.id, golf_course_id=otro, display_order=2
            )
        )
        async with e.uow:
            await e.uow.competitions.update(e.competicion)
        await e.crear(_hoja("09:00", "12:00"))
        tarde = await e.crear(_hoja("10:00", "13:00"), sesion="AFTERNOON", campo=otro)

        with pytest.raises(FranjaInvalidaError, match="MORNING"):
            await e.cambiar(tarde.id, golf_course_id=e.campo.value)

    async def test_el_formato_de_una_franja_no(self, e):
        await e.torneo()
        creada = await e.crear(_hoja())

        with pytest.raises(FranjaInvalidaError, match="formato"):
            await e.cambiar(creada.id, match_format="FOURBALL")

    async def test_a_una_sesion_de_ryder_no_se_le_pone_hoja(self, e):
        await e.torneo(TournamentType.RYDER_CUP)
        creada = await e.crear(formato="SINGLES")

        with pytest.raises(FranjaInvalidaError, match="Ryder"):
            await e.cambiar(creada.id, tee_sheet=_hoja())

    async def test_en_juego_ya_no(self, e):
        await e.torneo()
        creada = await e.crear(_hoja())
        await e.poner_estado(CompetitionStatus.IN_PROGRESS)

        with pytest.raises(AgendaNotEditableError, match="iniciar"):
            await e.cambiar(creada.id, tee_sheet=_hoja("10:00", "12:00"))


class TestBorrarYAgenda:
    async def test_borrar_en_juego_ya_no(self, e):
        await e.torneo()
        creada = await e.crear(_hoja())
        await e.poner_estado(CompetitionStatus.IN_PROGRESS)

        with pytest.raises(AgendaNotEditableError, match="iniciar"):
            await DeleteRoundUseCase(e.uow).execute(
                DeleteRoundRequestDTO(round_id=creada.id), e.creador
            )

    async def test_la_agenda_en_modo_manual_si_vale_en_stroke_play(self, e):
        """CodeRabbit en la #508: el modo manual solo dice «créalas una a una»."""
        await e.torneo()

        respuesta = await ConfigureScheduleUseCase(e.uow).execute(
            ConfigureScheduleRequestDTO(
                competition_id=e.competicion.id.value, mode=ScheduleConfigMode.MANUAL
            ),
            e.creador,
        )

        assert respuesta.mode == "MANUAL"

    async def test_la_agenda_en_stroke_play_en_juego_ya_no(self, e):
        await e.torneo(status=CompetitionStatus.IN_PROGRESS)

        with pytest.raises(AgendaNotEditableError, match="iniciar"):
            await ConfigureScheduleUseCase(e.uow).execute(
                ConfigureScheduleRequestDTO(
                    competition_id=e.competicion.id.value, mode=ScheduleConfigMode.MANUAL
                ),
                e.creador,
            )

    async def test_la_agenda_automatica_es_de_la_ryder(self, e):
        await e.torneo()

        with pytest.raises(FranjaInvalidaError, match="Ryder"):
            await ConfigureScheduleUseCase(e.uow).execute(
                ConfigureScheduleRequestDTO(
                    competition_id=e.competicion.id.value,
                    mode=ScheduleConfigMode.AUTOMATIC,
                    total_sessions=2,
                    sessions_per_day=1,
                ),
                e.creador,
            )


class TestElCalendario:
    async def test_cada_franja_con_su_hoja_horas_y_cupo_y_el_total(self, e):
        await e.torneo()
        await e.crear(_hoja("09:00", "09:20", partida=4))
        await e.crear(_hoja("15:00", "15:10", partida=3), sesion="AFTERNOON")

        calendario = await GetScheduleUseCase(e.uow).execute(
            GetScheduleRequestDTO(competition_id=e.competicion.id.value)
        )

        manana, tarde = calendario.days[0].rounds
        assert manana.tee_sheet.tee_times == [time(9, 0), time(9, 10), time(9, 20)]
        assert manana.tee_sheet.capacity == 12
        assert tarde.tee_sheet.capacity == 6
        assert calendario.tee_sheet_capacity == 18

    async def test_en_una_ryder_no_hay_cupo_de_franjas(self, e):
        await e.torneo(TournamentType.RYDER_CUP)
        await e.crear(formato="SINGLES")

        calendario = await GetScheduleUseCase(e.uow).execute(
            GetScheduleRequestDTO(competition_id=e.competicion.id.value)
        )

        assert calendario.tee_sheet_capacity is None
        assert calendario.days[0].rounds[0].tee_sheet is None
