"""
La agenda se edita desde que la competición existe (BE #365, mitad de FE #654).

Crear, cambiar y borrar sesiones exigía la competición CERRADA: una regla del
sprint de febrero que no salió de ninguna decisión. El diseño del 20 sep dice
lo contrario: **lo que se protege es tocar una sesión ya jugada, y ese límite
es de la sesión, no un estado global**. Y la agenda se propone al crear la
competición, cuando todavía está abierta.

    #    caso                                                     | qué pasa
    -----|--------------------------------------------------------|-----------------------------
    A1   crear una sesión con las inscripciones abiertas          | se crea, esperando equipos
    A2   crear una en una que espera su hora de apertura          | se crea
    A3   crear la del domingo con el torneo ya en juego           | se crea, esperando partidos
    A4   crear en una terminada o cancelada                       | no
    A5   cambiar el formato con las inscripciones abiertas        | se cambia
    A6   cambiar una sesión que ya tiene partidos                 | no (la regla de la sesión)
    A7   borrar con las inscripciones abiertas                    | se borra
    A8   la agenda automática con las inscripciones abiertas      | la propone, esperando equipos
    A9   la agenda automática con los equipos ya hechos           | nace esperando PARTIDOS
    A10  la agenda automática con alguna sesión ya con partidos   | no: no borra lo que hay
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    ConfigureScheduleRequestDTO,
    CreateRoundRequestDTO,
    DeleteRoundRequestDTO,
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotClosedError,
    RoundNotModifiableError,
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
from src.modules.competition.application.use_cases.update_round_use_case import (
    UpdateRoundUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.schedule_config_mode import (
    ScheduleConfigMode,
)
from src.modules.competition.domain.value_objects.team_assignment import (
    TeamAssignment as TeamAssignmentVO,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


async def _montar(estado="ACTIVE", con_equipos=False, apertura_programada=False):
    """Una competición del 1 al 3 de junio con un campo, en el estado pedido."""
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    campo = GolfCourseId(uuid4())
    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=organizador,
        name=CompetitionName("Agenda"),
        dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        max_players=24,
        team_assignment=TeamAssignmentVO.MANUAL,
        team_1_name="Europa",
        team_2_name="Estados Unidos",
    )
    competicion._golf_courses.append(
        CompetitionGolfCourse.create(
            competition_id=competicion.id, golf_course_id=campo, display_order=1
        )
    )
    if not apertura_programada and competicion.is_draft():
        competicion.activate()
    if estado in ("CLOSED", "IN_PROGRESS", "COMPLETED"):
        competicion.close_enrollments()
    if estado in ("IN_PROGRESS", "COMPLETED"):
        competicion.start()
    if estado == "COMPLETED":
        competicion.complete()
    if estado == "CANCELLED":
        competicion.cancel()

    async with uow:
        await uow.competitions.add(competicion)
        if con_equipos:
            jugadores = [UserId(uuid4()) for _ in range(4)]
            await uow.team_assignments.add(
                TeamAssignment.create(
                    competition_id=competicion.id,
                    mode=TeamAssignmentMode.MANUAL,
                    team_a_player_ids=jugadores[:2],
                    team_b_player_ids=jugadores[2:],
                )
            )
    return uow, competicion, organizador, campo


async def _crear(uow, competicion, organizador, campo, dia=1, franja="MORNING"):
    return await CreateRoundUseCase(uow=uow).execute(
        CreateRoundRequestDTO(
            competition_id=competicion.id.value,
            golf_course_id=campo.value,
            round_date=date(2026, 6, dia),
            session_type=franja,
            match_format="FOURBALL",
        ),
        organizador,
    )


async def _estado_de(uow, round_id):
    async with uow:
        return (await uow.rounds.find_by_id(RoundId(round_id))).status


class TestCrearSesiones:
    async def test_a1_con_las_inscripciones_abiertas(self):
        uow, competicion, organizador, campo = await _montar("ACTIVE")

        creada = await _crear(uow, competicion, organizador, campo)

        assert creada.status == "PENDING_TEAMS"

    async def test_a2_en_una_que_espera_su_hora_de_apertura(self):
        uow, competicion, organizador, campo = await _montar(apertura_programada=True)
        assert competicion.is_draft()

        creada = await _crear(uow, competicion, organizador, campo)

        assert creada.status == "PENDING_TEAMS"

    async def test_a3_la_del_domingo_con_el_torneo_ya_en_juego(self):
        uow, competicion, organizador, campo = await _montar("IN_PROGRESS", con_equipos=True)

        creada = await _crear(uow, competicion, organizador, campo, dia=3)

        assert creada.status == "PENDING_MATCHES"

    @pytest.mark.parametrize("estado", ["COMPLETED", "CANCELLED"])
    async def test_a4_en_una_terminada_o_cancelada_no(self, estado):
        uow, competicion, organizador, campo = await _montar(estado)

        with pytest.raises(CompetitionNotClosedError):
            await _crear(uow, competicion, organizador, campo)


class TestCambiarYBorrar:
    async def test_a5_cambiar_el_formato_con_las_inscripciones_abiertas(self):
        uow, competicion, organizador, campo = await _montar("ACTIVE")
        creada = await _crear(uow, competicion, organizador, campo)

        await UpdateRoundUseCase(uow).execute(
            UpdateRoundRequestDTO(round_id=creada.id, match_format="SINGLES"), organizador
        )

        async with uow:
            ronda = await uow.rounds.find_by_id(RoundId(creada.id))
        assert ronda.match_format.value == "SINGLES"

    async def test_a6_una_sesion_con_partidos_no_se_toca(self):
        uow, competicion, organizador, campo = await _montar("IN_PROGRESS", con_equipos=True)
        creada = await _crear(uow, competicion, organizador, campo)
        async with uow:
            ronda = await uow.rounds.find_by_id(RoundId(creada.id))
            ronda.mark_matches_generated()
            await uow.rounds.update(ronda)

        with pytest.raises(RoundNotModifiableError):
            await UpdateRoundUseCase(uow).execute(
                UpdateRoundRequestDTO(round_id=creada.id, match_format="SINGLES"), organizador
            )

    async def test_a7_borrar_con_las_inscripciones_abiertas(self):
        uow, competicion, organizador, campo = await _montar("ACTIVE")
        creada = await _crear(uow, competicion, organizador, campo)

        borrada = await DeleteRoundUseCase(uow).execute(
            DeleteRoundRequestDTO(round_id=creada.id), organizador
        )

        assert borrada.deleted is True

    @pytest.mark.parametrize("estado", ["COMPLETED", "CANCELLED"])
    async def test_a7_en_una_terminada_o_cancelada_ni_cambiar_ni_borrar(self, estado):
        uow, competicion, organizador, campo = await _montar("ACTIVE")
        creada = await _crear(uow, competicion, organizador, campo)
        async with uow:
            guardada = await uow.competitions.find_by_id(competicion.id)
            if estado == "COMPLETED":
                guardada.close_enrollments()
                guardada.start()
                guardada.complete()
            else:
                guardada.cancel()
            await uow.competitions.update(guardada)

        with pytest.raises(CompetitionNotClosedError):
            await UpdateRoundUseCase(uow).execute(
                UpdateRoundRequestDTO(round_id=creada.id, match_format="SINGLES"), organizador
            )
        with pytest.raises(CompetitionNotClosedError):
            await DeleteRoundUseCase(uow).execute(
                DeleteRoundRequestDTO(round_id=creada.id), organizador
            )


class TestLaAgendaAutomatica:
    async def _configurar(self, uow, competicion, organizador, sesiones=3, por_dia=2):
        return await ConfigureScheduleUseCase(uow).execute(
            ConfigureScheduleRequestDTO(
                competition_id=competicion.id.value,
                mode=ScheduleConfigMode.AUTOMATIC,
                total_sessions=sesiones,
                sessions_per_day=por_dia,
            ),
            organizador,
        )

    async def test_a8_la_propone_con_las_inscripciones_abiertas(self):
        uow, competicion, organizador, _ = await _montar("ACTIVE")

        respuesta = await self._configurar(uow, competicion, organizador)

        assert respuesta.rounds_created == 3
        async with uow:
            rondas = await uow.rounds.find_by_competition(competicion.id)
        assert {r.status for r in rondas} == {RoundStatus.PENDING_TEAMS}

    async def test_a9_con_los_equipos_hechos_nacen_esperando_partidos(self):
        uow, competicion, organizador, _ = await _montar("CLOSED", con_equipos=True)

        await self._configurar(uow, competicion, organizador)

        async with uow:
            rondas = await uow.rounds.find_by_competition(competicion.id)
        assert {r.status for r in rondas} == {RoundStatus.PENDING_MATCHES}

    async def test_a10_con_alguna_sesion_con_partidos_no_borra_lo_que_hay(self):
        uow, competicion, organizador, campo = await _montar("CLOSED", con_equipos=True)
        creada = await _crear(uow, competicion, organizador, campo)
        async with uow:
            ronda = await uow.rounds.find_by_id(RoundId(creada.id))
            ronda.mark_matches_generated()
            await uow.rounds.update(ronda)

        from src.modules.competition.application.use_cases.configure_schedule_use_case import (
            ScheduleAlreadyInPlayError,
        )

        with pytest.raises(ScheduleAlreadyInPlayError):
            await self._configurar(uow, competicion, organizador)

        assert await _estado_de(uow, creada.id) == RoundStatus.SCHEDULED
