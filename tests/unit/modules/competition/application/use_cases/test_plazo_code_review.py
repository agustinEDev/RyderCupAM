"""
El /code-review del plazo de inscripción y dos decisiones más de Agustín (16 nov 2026).

| Caso | Situación                                                         | Qué pasa                                       |
|------|-------------------------------------------------------------------|------------------------------------------------|
| O3   | el organizador pulsa «Activar» en una programada con el plazo     | abierta ahora: exenta, como reabrir (R1)        |
|      | pasado                                                            |                                                |
| O3   | ... invitar sola no la abre exenta                                | ENROLLMENT_DEADLINE_PASSED                      |
| O4   | se mueve una cerrada por el plazo con actualización programada    | la actualización se mueve los mismos días, a    |
|      |                                                                   | la misma hora del campo                         |
| O4   | ... sin actualización programada                                  | no se programa ninguna                          |
| D1   | una sesión de Ryder a la que ya le llegó su hora (reloj)          | no se mueve nada (400)                          |
| D1   | una franja cuya primera salida ya pasó                            | no se mueve nada                                |
| D1   | una franja con una partida empezada                               | no se mueve nada                                |
| D2   | cerrar falla por otra cosa                                        | ERROR con traza la primera vez; luego DEBUG     |
| D3   | ACTIVE sin fecha de apertura (de la release anterior), plazo pasado | la vuelta la apunta ahora: exenta, no se cierra |
| D3   | ... con el plazo en el futuro                                     | apuntada ahora: se cerrará en su plazo          |
| D3   | la entidad, sin fecha de apertura                                 | cuenta como abierta a tiempo                    |
| D4   | el aviso «no se puede cerrar» se decide y publica con la fila     | bloqueada → publicar → apuntar, en ese orden    |
|      | bloqueada                                                         |                                                |
| D5   | países acompañantes en otro orden                                 | no es un cambio                                 |
| D6   | un fallo conocido que ya no es candidata                          | se olvida                                       |
| D7   | se cierra o se mueve sin aviso apuntado                           | no se retira nada                               |
| D7   | ... con aviso apuntado                                            | se retira                                       |
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    CloseEnrollmentsRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.services.handicaps_al_cerrar import (
    PlayersWithoutHandicapError,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_past_deadline_use_case import (
    CloseEnrollmentsPastDeadlineUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.jugador_de_partida import JugadorDePartida
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

MADRID = ZoneInfo("Europe/Madrid")
HOY = datetime.now(UTC).date()
TORNEO = HOY + timedelta(days=2)
MANANA = datetime.combine(TORNEO - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
ANTES = MANANA - timedelta(days=5)
DESPUES = MANANA + timedelta(hours=14)


class _Zonas:
    async def for_competition(self, competition):
        return "Europe/Madrid"

    async def for_course(self, golf_course_id):
        return "Europe/Madrid"


class _Avisos:
    def __init__(self):
        self.avisos: list[tuple] = []

    def __getattr__(self, nombre):
        async def apunta(competition=None, *args, **_kwargs):
            self.avisos.append((nombre, getattr(competition, "id", competition)))

        return apunta


class _Campos:
    async def find_by_id(self, _id):
        return None


def _plazo(ahora: datetime) -> PlazoDeInscripcion:
    return PlazoDeInscripcion(_Zonas(), reloj=lambda: ahora)


async def _competicion(
    uow, abierta: datetime | None = ANTES, dias: int | None = None, inicio: date = TORNEO
) -> Competition:
    competition = Competition.create(
        id=CompetitionId.generate(),
        creator_id=UserId.generate(),
        name=CompetitionName(f"Copa {uuid4().hex[:6]}"),
        dates=DateRange(inicio, inicio + timedelta(days=1)),
        location=Location(main_country="ES", adjacent_country_1="FR", adjacent_country_2="PT"),
        team_1_name="Europa",
        team_2_name="USA",
        play_mode=PlayMode.SCRATCH,
        max_players=24,
        visibility=Visibility.PUBLIC,
        enrollment_opens_days_before=dias,
    )
    if abierta is not None:
        competition.activate(now=abierta)
    async with uow:
        await uow.competitions.add(competition)
    return competition


async def _cerrada_por_el_plazo(uow) -> Competition:
    competition = await _competicion(uow)
    competition.close_enrollments(by_deadline=True)
    return competition


def _mover(uow, ahora=DESPUES, avisos=None) -> UpdateCompetitionUseCase:
    return UpdateCompetitionUseCase(
        uow, LocationBuilder(uow.countries), _Campos(), actividad=avisos, plazo=_plazo(ahora)
    )


def _fechas(dias: int, **mas) -> UpdateCompetitionRequestDTO:
    inicio = TORNEO + timedelta(days=dias)
    return UpdateCompetitionRequestDTO(start_date=inicio, end_date=inicio + timedelta(1), **mas)


class TestO3ActivarAMano:
    async def test_pasado_el_plazo_activar_la_deja_abierta_y_exenta(self):
        """
        O3. Given programada (su apertura y su plazo ya pasaron)
        When el organizador pulsa «Activar»
        Then se abre ahora y queda exenta, como al reabrir pasado el plazo
        """
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow, abierta=None, dias=5, inicio=HOY)
        antes = datetime.now(UTC).replace(tzinfo=None)

        await ActivateCompetitionUseCase(uow).execute(
            ActivateCompetitionRequestDTO(competition_id=competition.id.value),
            competition.creator_id,
        )

        assert competition.status is CompetitionStatus.ACTIVE
        assert competition.enrollment_opened_at >= antes
        plazo = PlazoDeInscripcion(_Zonas(), reloj=lambda: datetime.now(UTC))
        assert await plazo.vencido(competition) is False


class TestO4LaActualizacionProgramada:
    async def test_se_mueve_los_mismos_dias_a_la_misma_hora_del_campo(self):
        """
        O4. Given cerrada por el plazo, con la actualización de hándicaps a las 9:00 del
        día antes del torneo (hora de Madrid)
        When se mueve el torneo 200 días (cruza un cambio de hora)
        Then la actualización queda 200 días después, a las 9:00 de Madrid
        """
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        para = datetime.combine(TORNEO - timedelta(days=1), time(9, 0), tzinfo=MADRID)
        async with uow:
            await uow.handicap_updates.programar(competition.id, para.astimezone(UTC), ANTES)

        await _mover(uow).execute(competition.id, _fechas(200), competition.creator_id)

        async with uow:
            movida = await uow.handicap_updates.programada_de(competition.id)
        local = movida.astimezone(MADRID)
        assert local.date() == TORNEO - timedelta(days=1) + timedelta(days=200)
        assert local.time() == time(9, 0)

    async def test_sin_programada_no_se_programa_ninguna(self):
        """O4. Given sin actualización programada / When se mueve / Then sigue sin ninguna."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)

        await _mover(uow).execute(competition.id, _fechas(7), competition.creator_id)

        async with uow:
            assert await uow.handicap_updates.programada_de(competition.id) is None


async def _sesion(uow, competition: Competition, dia: date = TORNEO) -> Round:
    ronda = Round.create(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=dia,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    async with uow:
        await uow.rounds.add(ronda)
    return ronda


async def _franja(uow, competition: Competition, dia: date = TORNEO) -> Round:
    franja = Round.create_franja(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=dia,
        session_type=SessionType.AFTERNOON,
        hoja_de_salidas=HojaDeSalidas(time(15, 0), time(16, 0), 10, 4),
    )
    async with uow:
        await uow.rounds.add(franja)
    return franja


def _jugador() -> JugadorDePartida:
    return JugadorDePartida(
        user_id=UserId.generate(),
        handicap=Decimal("0"),
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        tee_gender=Gender.MALE,
        golpes_por_hoyo=(0,) * 18,
        par_por_hoyo=(4,) * 18,
    )


class TestD1LoJugadoPorElReloj:
    async def test_una_sesion_a_la_que_le_llego_su_hora_no_se_mueve(self):
        """
        D1. Given una sesión de mañana el día del torneo (abre a las 6:00 de Madrid)
        When se intenta mover a las 8:00 UTC de ese día
        Then no se mueve nada
        """
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        ronda = await _sesion(uow, competition)
        ahora = datetime.combine(TORNEO, time(8, 0), tzinfo=UTC)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow, ahora=ahora).execute(
                competition.id, _fechas(7), competition.creator_id
            )

        assert ronda.round_date == TORNEO
        assert competition.dates.start_date == TORNEO

    async def test_una_franja_cuya_primera_salida_ya_paso_no_se_mueve(self):
        """D1. Given una franja de las 15:00 de Madrid / When a las 15:30 UTC / Then nada."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        franja = await _franja(uow, competition)
        ahora = datetime.combine(TORNEO, time(15, 30), tzinfo=UTC)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow, ahora=ahora).execute(
                competition.id, _fechas(7), competition.creator_id
            )

        assert franja.round_date == TORNEO

    async def test_una_franja_con_una_partida_empezada_no_se_mueve(self):
        """D1. Given una partida de la franja ya empezada (antes de su hora) / Then nada."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        franja = await _franja(uow, competition, dia=TORNEO + timedelta(days=1))
        partida = Partida.crear(competition.id, franja.id, 1, [_jugador()])
        partida.empezar()
        async with uow:
            await uow.partidas.anadir([partida])

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow).execute(competition.id, _fechas(7), competition.creator_id)

        assert franja.round_date == TORNEO + timedelta(days=1)

    async def test_antes_de_su_hora_si_se_mueve(self):
        """D1. Given una sesión del día del torneo / When se mueve el día antes / Then se mueve."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        ronda = await _sesion(uow, competition)

        await _mover(uow).execute(competition.id, _fechas(7), competition.creator_id)

        assert ronda.round_date == TORNEO + timedelta(days=7)


class _NoSeCierra:
    def __init__(self, error: Exception):
        self._error = error

    async def cerrar_por_el_plazo(self, competition_id):
        raise self._error


class TestD2ElPrimerFalloEsUnError:
    async def test_error_con_traza_y_luego_debug(self, caplog):
        """D2. Given cerrar revienta siempre / When tres vueltas / Then un ERROR y luego DEBUG."""
        uow = InMemoryUnitOfWork()
        await _competicion(uow)
        conocidos: set = set()

        with caplog.at_level(logging.DEBUG):
            for _ in range(3):
                await CloseEnrollmentsPastDeadlineUseCase(
                    uow,
                    _NoSeCierra(RuntimeError("roto")),
                    _plazo(DESPUES),
                    fallos_conocidos=conocidos,
                ).execute()

        errores = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert [r.levelno for r in errores] == [logging.ERROR]
        assert errores[0].exc_info is not None
        assert (
            len(
                [
                    r
                    for r in caplog.records
                    if r.levelno == logging.DEBUG and "Still" in r.getMessage()
                ]
            )
            == 2
        )


class TestD3SinFechaDeApertura:
    def test_la_entidad_la_cuenta_abierta_a_tiempo(self):
        """D3. Given ACTIVE sin fecha de apertura y modificada tarde / Then cerrada: a tiempo."""
        competition = Competition.create(
            id=CompetitionId.generate(),
            creator_id=UserId.generate(),
            name=CompetitionName("Copa"),
            dates=DateRange(TORNEO, TORNEO + timedelta(days=1)),
            location=Location(main_country="ES"),
            team_1_name="A",
            team_2_name="B",
            play_mode=PlayMode.SCRATCH,
        )
        competition.activate(now=ANTES)
        competition._enrollment_opened_at = None
        competition._updated_at = DESPUES.replace(tzinfo=None)

        assert competition.entries_closed_by_deadline("Europe/Madrid", DESPUES) is True

    async def test_la_vuelta_apunta_ahora_y_pasado_el_plazo_queda_exenta(self):
        """D3. Given ACTIVE sin fecha, plazo pasado / When pasa la vuelta / Then apuntada, abierta."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition._enrollment_opened_at = None

        await CloseEnrollmentsPastDeadlineUseCase(
            uow,
            CloseEnrollmentsUseCase(uow, USUARIOS_CON_GENERO, plazo=_plazo(DESPUES)),
            _plazo(DESPUES),
        ).execute()

        assert competition.enrollment_opened_at == DESPUES.replace(tzinfo=None)
        assert competition.status is CompetitionStatus.ACTIVE

    async def test_con_el_plazo_en_el_futuro_se_cerrara_a_su_hora(self):
        """D3. Given ACTIVE sin fecha, plazo futuro / When vuelta ahora y tras el plazo / Then cierra."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition._enrollment_opened_at = None
        temprano = ANTES

        await CloseEnrollmentsPastDeadlineUseCase(
            uow,
            CloseEnrollmentsUseCase(uow, USUARIOS_CON_GENERO, plazo=_plazo(temprano)),
            _plazo(temprano),
        ).execute()
        assert competition.enrollment_opened_at == temprano.replace(tzinfo=None)

        await CloseEnrollmentsPastDeadlineUseCase(
            uow,
            CloseEnrollmentsUseCase(uow, USUARIOS_CON_GENERO, plazo=_plazo(DESPUES)),
            _plazo(DESPUES),
        ).execute()
        assert competition.status is CompetitionStatus.CLOSED

    async def test_fuera_de_la_ventana_tambien(self):
        """D3. Given ACTIVE sin fecha de un torneo dentro de un mes / Then también se apunta."""
        uow = InMemoryUnitOfWork()
        lejana = await _competicion(uow, inicio=TORNEO + timedelta(days=30))
        lejana._enrollment_opened_at = None

        await CloseEnrollmentsPastDeadlineUseCase(
            uow, _NoSeCierra(RuntimeError("no se llama")), _plazo(DESPUES)
        ).execute()

        assert lejana.enrollment_opened_at == DESPUES.replace(tzinfo=None)


class TestD4ConLaFilaBloqueada:
    async def test_bloquear_publicar_y_apuntar_en_ese_orden(self):
        """D4. Given no se puede cerrar / When se avisa / Then con la fila bloqueada durante todo."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        orden: list[str] = []
        bloquea = uow.competitions.find_by_id_for_update

        async def bloqueada(competition_id):
            orden.append("bloquea")
            return await bloquea(competition_id)

        uow.competitions.find_by_id_for_update = bloqueada
        original_commit = uow.commit

        async def commit():
            orden.append("confirma")
            await original_commit()

        uow.commit = commit

        class _Publica:
            async def close_blocked(self, competition, reason, players):
                orden.append("publica")

        await CloseEnrollmentsPastDeadlineUseCase(
            uow,
            _NoSeCierra(PlayersWithoutHandicapError([SimpleNamespace(user_id=None, name="A")])),
            _plazo(DESPUES),
            actividad=_Publica(),
        ).execute()

        assert orden[orden.index("bloquea") :][:3] == ["bloquea", "publica", "confirma"]
        assert competition.close_blocked_notified is True


class TestD5PaisesComoConjunto:
    async def test_en_otro_orden_no_es_un_cambio(self):
        """D5. Given Francia y Portugal / When llegan Portugal y Francia / Then se mueve."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)

        await _mover(uow).execute(
            competition.id,
            _fechas(7, adjacent_country_1="PT", adjacent_country_2="FR"),
            competition.creator_id,
        )

        assert competition.dates.start_date == TORNEO + timedelta(days=7)


class TestD6LosFallosConocidosSeOlvidan:
    async def test_la_que_ya_no_es_candidata(self):
        """D6. Given un fallo conocido de una que ya no está abierta / Then se olvida."""
        uow = InMemoryUnitOfWork()
        cerrada = await _competicion(uow)
        cerrada.close_enrollments()
        conocidos = {cerrada.id, CompetitionId.generate()}

        await CloseEnrollmentsPastDeadlineUseCase(
            uow, _NoSeCierra(RuntimeError("x")), _plazo(DESPUES), fallos_conocidos=conocidos
        ).execute()

        assert conocidos == set()


class TestD7SoloSiPuedeHaberAviso:
    @pytest.mark.parametrize("avisada", [True, False])
    async def test_al_cerrar(self, avisada):
        """D7. Given con o sin aviso apuntado / When se cierra / Then se retira solo si lo había."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        if avisada:
            competition.mark_close_blocked_notified()
        avisos = _Avisos()

        await CloseEnrollmentsUseCase(uow, USUARIOS_CON_GENERO, actividad=avisos).execute(
            CloseEnrollmentsRequestDTO(competition_id=competition.id.value),
            competition.creator_id,
        )

        assert (("close_block_withdrawn", competition.id) in avisos.avisos) is avisada

    @pytest.mark.parametrize("avisada", [True, False])
    async def test_al_mover_una_abierta(self, avisada):
        """D7. Given ACTIVE con o sin aviso / When se mueven sus fechas / Then solo si lo había."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        if avisada:
            competition.mark_close_blocked_notified()
        avisos = _Avisos()

        await _mover(uow, avisos=avisos).execute(competition.id, _fechas(7), competition.creator_id)

        assert (("close_block_withdrawn", competition.id) in avisos.avisos) is avisada


class TestD3ElApunteSoloSiHaceFalta:
    def _abierta(self) -> Competition:
        competition = Competition.create(
            id=CompetitionId.generate(),
            creator_id=UserId.generate(),
            name=CompetitionName("Copa"),
            dates=DateRange(TORNEO, TORNEO + timedelta(days=1)),
            location=Location(main_country="ES"),
            team_1_name="A",
            team_2_name="B",
            play_mode=PlayMode.SCRATCH,
        )
        competition.activate(now=ANTES)
        return competition

    def test_con_fecha_no_se_toca(self):
        """D3. Given ACTIVE con su fecha de apertura / Then no se apunta otra."""
        competition = self._abierta()

        assert competition.record_unknown_opening(DESPUES) is False
        assert competition.enrollment_opened_at == ANTES.replace(tzinfo=None)

    def test_si_no_esta_abierta_no(self):
        """D3. Given CLOSED sin fecha / Then no se apunta: solo las ACTIVE."""
        competition = self._abierta()
        competition.close_enrollments()
        competition._enrollment_opened_at = None

        assert competition.record_unknown_opening(DESPUES) is False
        assert competition.enrollment_opened_at is None


class TestD5UnHuecoSuelto:
    async def test_cambiar_un_acompanante_es_un_cambio(self):
        """D5. Given Francia y Portugal / When llega solo `adjacent_country_1: IT` / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow).execute(
                competition.id, _fechas(7, adjacent_country_1="IT"), competition.creator_id
            )


class TestD1LaSesionEnJuegoAntesDeSuHora:
    async def test_en_juego_cuenta_como_empezada(self):
        """D1. Given una sesión puesta en juego a mano antes de su hora / Then empezada."""
        from src.modules.competition.application.services.mover_el_torneo import (
            alguna_sesion_empezada,
        )
        from src.modules.competition.domain.value_objects.round_status import RoundStatus

        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        ronda = await _sesion(uow, competition, TORNEO + timedelta(days=10))
        assert await alguna_sesion_empezada(uow, [ronda], _Zonas(), DESPUES) is False

        ronda._status = RoundStatus.IN_PROGRESS

        assert await alguna_sesion_empezada(uow, [ronda], _Zonas(), DESPUES) is True
