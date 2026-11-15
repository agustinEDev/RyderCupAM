"""
Las revisiones del plazo de inscripción y dos decisiones más de Agustín (16 nov 2026).

| Caso | Situación                                                         | Qué pasa                                       |
|------|-------------------------------------------------------------------|------------------------------------------------|
| O1   | cerrada por el plazo, se mueve el torneo 7 días                   | sus sesiones y franjas se mueven 7 días, con   |
|      |                                                                   | sus plazas; y si queda plazo, se reabre         |
| O1   | ... hacia atrás, con sesiones en días seguidos                    | se mueven todas, sin chocar entre ellas        |
| O1   | ... y el torneo nuevo es más corto y deja una sesión fuera        | DatesLeaveSessionsOutError, nada se mueve      |
| O1   | ... con una sesión ya jugada (en juego o terminada)               | no se mueve nada                               |
| O2   | al reabrirse así                                                  | se retira el aviso «se han cerrado» (y los de  |
|      |                                                                   | la RFEG, como al reabrir, #864)                 |
| F1   | la app manda el formulario entero con los mismos valores          | se acepta: solo cambian las fechas             |
| F1   | ... con algún valor distinto                                      | CompetitionNotEditableError                    |
| F2   | se cierra (a mano o por el plazo) sin aviso apuntado               | se retira igual el «no se puede cerrar»        |
| F2   | se mueven las fechas de una abierta                               | se retira el «no se puede cerrar»              |
| F2   | ... o se cambia otra cosa                                         | no se retira nada                              |
| F3   | publicar el «no se puede cerrar» falla                            | no queda apuntado: la vuelta siguiente avisa   |
| F4   | cerrar una revienta por otra cosa, vuelta tras vuelta             | un WARNING con traza la primera vez; luego no  |
| F5   | ACTIVE sin fecha de apertura: ver D3 en test_plazo_code_review    | la vuelta la apunta                            |
| F6   | ACTIVE de hace más de 30 días, o abierta seguro tras el plazo     | ni se lee                                      |
| F7   | invitar a una programada a la que ya le tocaba abrirse            | se abre a su hora programada: no exenta        |
| F7   | activar con el botón una a la que ya le tocaba (O3: ahora)        | se abre ahora: exenta si el plazo pasó         |
| F7   | invitar a una programada a la que todavía no le toca              | se abre ahora, como siempre                    |
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    CloseEnrollmentsRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.exceptions import NotCompetitionCreatorError  # noqa: F401
from src.modules.competition.application.services.plazo_de_inscripcion import (
    EnrollmentDeadlinePassedError,
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
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    CompetitionNotEditableError,
    DatesLeaveSessionsOutError,
    UpdateCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio

HOY = datetime.now(UTC).date()
TORNEO = HOY + timedelta(days=2)
MANANA = datetime.combine(TORNEO - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
ANTES = MANANA - timedelta(days=5)
DESPUES = MANANA + timedelta(hours=14)
TODAVIA = MANANA + timedelta(hours=8)


class _Zonas:
    async def for_competition(self, competition):
        return "Europe/Madrid"

    async def for_course(self, golf_course_id):
        return "Europe/Madrid"


class _Avisos:
    """El puerto de Actividad: apunta lo que interesa, y puede fallar en uno."""

    def __init__(self, falla_en: str | None = None):
        self.avisos: list[tuple] = []
        self._falla_en = falla_en

    def __getattr__(self, nombre):
        async def apunta(competition=None, *args, **_kwargs):
            if nombre == self._falla_en:
                raise RuntimeError("feed caído")
            if nombre in {
                "enrollments_closed",
                "enrollments_closed_withdrawn",
                "close_block_withdrawn",
                "close_blocked",
            }:
                self.avisos.append((nombre, competition.id))

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
        location=Location(main_country="ES"),
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


async def _sesion(uow, competition: Competition, dia: date, sesion=SessionType.MORNING) -> Round:
    ronda = Round.create(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=dia,
        session_type=sesion,
        match_format=MatchFormat.SINGLES,
    )
    async with uow:
        await uow.rounds.add(ronda)
    return ronda


async def _franja(uow, competition: Competition, dia: date) -> Round:
    franja = Round.create_franja(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=dia,
        session_type=SessionType.AFTERNOON,
        hoja_de_salidas=HojaDeSalidas(time(9, 0), time(10, 0), 10, 4),
    )
    async with uow:
        await uow.rounds.add(franja)
    return franja


def _mover(uow, ahora=DESPUES, avisos=None) -> UpdateCompetitionUseCase:
    return UpdateCompetitionUseCase(
        uow, LocationBuilder(uow.countries), _Campos(), actividad=avisos, plazo=_plazo(ahora)
    )


def _fechas(dias: int, largo: int = 1, **mas) -> UpdateCompetitionRequestDTO:
    inicio = TORNEO + timedelta(days=dias)
    return UpdateCompetitionRequestDTO(
        start_date=inicio, end_date=inicio + timedelta(days=largo), **mas
    )


async def _fecha_de(uow, ronda: Round) -> date:
    async with uow:
        return (await uow.rounds.find_by_id(ronda.id)).round_date


class TestO1LasSesionesSeMuevenConElTorneo:
    async def test_sesiones_y_franjas_se_mueven_los_mismos_dias_con_sus_plazas(self):
        """
        O1. Given cerrada por el plazo con una sesión cada día y una franja con su plaza
        When se mueve una semana más tarde
        Then todo se mueve 7 días, la plaza sigue en su franja, y se reabre
        """
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        primera = await _sesion(uow, competition, TORNEO)
        segunda = await _sesion(uow, competition, TORNEO + timedelta(days=1))
        franja = await _franja(uow, competition, TORNEO)
        jugador = UserId.generate()
        async with uow:
            await uow.plazas.add(
                PlazaEnFranja.crear(competition.id, franja.id, jugador, datetime.now(UTC))
            )

        await _mover(uow).execute(competition.id, _fechas(7), competition.creator_id)

        assert await _fecha_de(uow, primera) == TORNEO + timedelta(days=7)
        assert await _fecha_de(uow, segunda) == TORNEO + timedelta(days=8)
        assert await _fecha_de(uow, franja) == TORNEO + timedelta(days=7)
        async with uow:
            plazas = await uow.plazas.de_la_competicion(competition.id)
        assert [(p.round_id, p.user_id) for p in plazas] == [(franja.id, jugador)]
        assert competition.status is CompetitionStatus.ACTIVE

    @pytest.mark.parametrize("dias", [-1, 1])
    async def test_un_dia_con_sesiones_en_dias_seguidos_sin_chocar(self, dias):
        """
        O1. Given sesiones el día 1 y el 2 (por la mañana)
        When se mueve un día (adelante o atrás)
        Then se mueven las dos, en el orden que no deja dos en el mismo día a la vez
        """
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        primera = await _sesion(uow, competition, TORNEO)
        segunda = await _sesion(uow, competition, TORNEO + timedelta(days=1))
        orden: list[date] = []
        original = uow.rounds.update

        async def apunta(ronda):
            orden.append(ronda.round_date)
            ocupados = [
                r.round_date
                for r in await uow.rounds.find_by_competition(competition.id)
                if r.id != ronda.id
            ]
            assert ronda.round_date not in ocupados, "dos sesiones el mismo día y sesión"
            await original(ronda)

        uow.rounds.update = apunta

        await _mover(uow).execute(competition.id, _fechas(dias), competition.creator_id)

        assert await _fecha_de(uow, primera) == TORNEO + timedelta(days=dias)
        assert await _fecha_de(uow, segunda) == TORNEO + timedelta(days=1 + dias)
        assert len(orden) == 2

    async def test_si_el_torneo_nuevo_deja_una_sesion_fuera_no_se_mueve_nada(self):
        """O1. Given sesiones dos días / When se mueve y se acorta a uno / Then nada se mueve."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        primera = await _sesion(uow, competition, TORNEO)
        segunda = await _sesion(uow, competition, TORNEO + timedelta(days=1))

        with pytest.raises(DatesLeaveSessionsOutError):
            await _mover(uow).execute(competition.id, _fechas(7, largo=0), competition.creator_id)

        assert await _fecha_de(uow, primera) == TORNEO
        assert await _fecha_de(uow, segunda) == TORNEO + timedelta(days=1)
        assert competition.dates.start_date == TORNEO

    @pytest.mark.parametrize("estado", [RoundStatus.IN_PROGRESS, RoundStatus.COMPLETED])
    async def test_con_una_sesion_jugada_no_se_mueve_nada(self, estado):
        """O1. Given una sesión ya en juego o terminada / Then no se mueve nada."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        jugada = await _sesion(uow, competition, TORNEO)
        jugada._status = estado
        otra = await _sesion(uow, competition, TORNEO + timedelta(days=1))

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow).execute(competition.id, _fechas(7), competition.creator_id)

        assert await _fecha_de(uow, otra) == TORNEO + timedelta(days=1)
        assert competition.dates.start_date == TORNEO

    async def test_la_sesion_sola_se_mueve(self):
        """O1. Given una sesión / When se le mueven los días / Then su fecha, y la hora de cambio."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        ronda = await _sesion(uow, competition, TORNEO)

        ronda.desplazar(3)

        assert ronda.round_date == TORNEO + timedelta(days=3)


class TestO2AlReabrirseSeRetiraElAvisoDeCerradas:
    async def test_reabierta_por_moverla_retira_el_aviso(self):
        """O2. Given cerrada por el plazo / When se mueve y se reabre / Then se retira el aviso."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        avisos = _Avisos()

        await _mover(uow, avisos=avisos).execute(competition.id, _fechas(7), competition.creator_id)

        assert ("enrollments_closed_withdrawn", competition.id) in avisos.avisos

    async def test_reabierta_por_moverla_retira_los_de_la_rfeg(self):
        """O2/#864. Given cerrada por el plazo / When se reabre al moverla / Then como al reabrir."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        async with uow:
            await uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId.generate(),
                    competition_id=competition.id,
                    user_id=UserId.generate(),
                )
            )
        retirados: list[str] = []

        class _Rfeg(_Avisos):
            async def handicaps_not_updated_withdrawn(self, competition):
                retirados.append("handicaps_not_updated")

            async def handicap_not_found_withdrawn(self, competition, user_ids):
                retirados.append("handicap_not_found")

        await _mover(uow, avisos=_Rfeg()).execute(
            competition.id, _fechas(7), competition.creator_id
        )

        assert retirados == ["handicaps_not_updated", "handicap_not_found"]

    async def test_movida_sin_reabrir_no_lo_retira(self):
        """O2. Given cerrada por el plazo / When se mueve y sigue cerrada / Then el aviso se queda."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        avisos = _Avisos()

        await _mover(uow, ahora=DESPUES + timedelta(days=30), avisos=avisos).execute(
            competition.id, _fechas(7), competition.creator_id
        )

        assert ("enrollments_closed_withdrawn", competition.id) not in avisos.avisos


class TestF1ElFormularioEntero:
    async def test_con_los_mismos_valores_se_acepta(self):
        """
        F1. Given cerrada por el plazo
        When la app manda el formulario entero (nombre, país, cupo, modo, equipos...) sin cambios
        Then se mueven las fechas
        """
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        formulario = {
            "name": f"  {competition.name.value}  ",
            "main_country": "ES",
            "countries": [],
            "play_mode": "SCRATCH",
            "visibility": "PUBLIC",
            "number_of_players": 24,
            "team_1_name": "Europa",
            "team_2_name": "USA",
            "setup_mode": competition.ryder_cup.setup_mode.value,
            "max_playing_handicap": None,
        }

        await _mover(uow).execute(
            competition.id,
            UpdateCompetitionRequestDTO(
                start_date=TORNEO + timedelta(days=7),
                end_date=TORNEO + timedelta(days=8),
                **formulario,
            ),
            competition.creator_id,
        )

        assert competition.dates.start_date == TORNEO + timedelta(days=7)

    @pytest.mark.parametrize(
        "cambio",
        [
            {"name": "Otro nombre"},
            {"main_country": "PT"},
            {"countries": ["FR"]},
            {"play_mode": "HANDICAP"},
            {"visibility": "PRIVATE"},
            {"number_of_players": 30},
            {"team_1_name": "Otros"},
            {"team_2_name": "Otros"},
            {"max_playing_handicap": 20},
            {"enrollment_opens_days_before": 5},
        ],
    )
    async def test_con_un_valor_distinto_no(self, cambio):
        """F1. Given cerrada por el plazo / When cambia algo más que las fechas / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow).execute(
                competition.id,
                UpdateCompetitionRequestDTO(
                    start_date=TORNEO + timedelta(days=7),
                    end_date=TORNEO + timedelta(days=8),
                    **cambio,
                ),
                competition.creator_id,
            )

        assert competition.dates.start_date == TORNEO


class TestF2ElAvisoDeBloqueoSeRetira:
    @pytest.mark.parametrize("por_el_plazo", [True, False])
    async def test_al_cerrar_siempre(self, por_el_plazo):
        """F2/D7. Given con aviso apuntado / When se cierra (por el plazo o a mano) / Then se retira."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition.mark_close_blocked_notified()
        avisos = _Avisos()
        caso = CloseEnrollmentsUseCase(
            uow, USUARIOS_CON_GENERO, actividad=avisos, plazo=_plazo(DESPUES)
        )

        if por_el_plazo:
            await caso.cerrar_por_el_plazo(competition.id)
        else:
            await caso.execute(
                CloseEnrollmentsRequestDTO(competition_id=competition.id.value),
                competition.creator_id,
            )

        assert ("close_block_withdrawn", competition.id) in avisos.avisos

    async def test_al_mover_las_fechas_de_una_abierta(self):
        """F2/D7. Given ACTIVE con aviso apuntado / When se mueven sus fechas / Then se retira."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition.mark_close_blocked_notified()
        avisos = _Avisos()

        await _mover(uow, avisos=avisos).execute(competition.id, _fechas(7), competition.creator_id)

        assert ("close_block_withdrawn", competition.id) in avisos.avisos

    async def test_cambiar_otra_cosa_no(self):
        """F2. Given ACTIVE avisada / When cambia el nombre (y las mismas fechas) / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        competition.mark_close_blocked_notified()
        avisos = _Avisos()

        await _mover(uow, avisos=avisos).execute(
            competition.id, _fechas(0, name="Otro nombre"), competition.creator_id
        )

        assert ("close_block_withdrawn", competition.id) not in avisos.avisos


class _NoSeCierra:
    def __init__(self, error: Exception):
        self._error = error
        self.veces = 0

    async def cerrar_por_el_plazo(self, competition_id):
        self.veces += 1
        raise self._error


class TestF3SoloApuntadoSiSePublico:
    async def test_si_publicar_falla_no_queda_apuntado_y_se_reintenta(self):
        """
        F3. Given cerrarla falla por hándicap y el feed está caído
        When pasan dos vueltas, la segunda con el feed arreglado
        Then la primera no apunta nada; la segunda avisa y apunta
        """
        from types import SimpleNamespace

        from src.modules.competition.application.services.handicaps_al_cerrar import (
            PlayersWithoutHandicapError,
        )

        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        cerrar = _NoSeCierra(
            PlayersWithoutHandicapError([SimpleNamespace(user_id=None, name="Ana")])
        )
        caido = _Avisos(falla_en="close_blocked")

        primera = await CloseEnrollmentsPastDeadlineUseCase(
            uow, cerrar, _plazo(DESPUES), actividad=caido
        ).execute()
        assert competition.close_blocked_notified is False
        assert primera.notified == 0

        bueno = _Avisos()
        segunda = await CloseEnrollmentsPastDeadlineUseCase(
            uow, cerrar, _plazo(DESPUES), actividad=bueno
        ).execute()
        assert competition.close_blocked_notified is True
        assert segunda.notified == 1
        assert ("close_blocked", competition.id) in bueno.avisos

    async def test_sin_publicador_no_se_apunta(self):
        """F3. Given sin Actividad / Then no se apunta: no se le dijo nada."""
        from types import SimpleNamespace

        from src.modules.competition.application.services.handicaps_al_cerrar import (
            PlayersWithoutHandicapError,
        )

        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        cerrar = _NoSeCierra(
            PlayersWithoutHandicapError([SimpleNamespace(user_id=None, name="Ana")])
        )

        await CloseEnrollmentsPastDeadlineUseCase(uow, cerrar, _plazo(DESPUES)).execute()

        assert competition.close_blocked_notified is False


class TestF4OtrosFallosSinRepetirLaTraza:
    async def test_la_traza_una_vez_y_luego_sin_ruido(self, caplog):
        """
        F4. Given cerrar una revienta siempre por otra cosa
        When pasan tres vueltas con la misma memoria de fallos
        Then un ERROR con traza la primera (D2: llega a Sentry); las demás, nada a WARNING
        """
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        cerrar = _NoSeCierra(RuntimeError("roto"))
        conocidos: set = set()

        with caplog.at_level(logging.DEBUG):
            for _ in range(3):
                resumen = await CloseEnrollmentsPastDeadlineUseCase(
                    uow, cerrar, _plazo(DESPUES), fallos_conocidos=conocidos
                ).execute()

        avisos = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert [a.levelno for a in avisos] == [logging.ERROR]
        assert avisos[0].exc_info is not None
        assert str(competition.id) in avisos[0].getMessage()
        assert cerrar.veces == 3
        assert resumen.failed == 1

    async def test_si_luego_se_cierra_se_olvida(self):
        """F4. Given falló antes / When se cierra bien / Then deja de estar entre los fallos."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow)
        conocidos: set = {competition.id}

        class _Cierra:
            async def cerrar_por_el_plazo(self, competition_id):
                return object()

        await CloseEnrollmentsPastDeadlineUseCase(
            uow, _Cierra(), _plazo(DESPUES), fallos_conocidos=conocidos
        ).execute()

        assert conocidos == set()


class TestF6LasQueNiSeLeen:
    async def test_ni_las_viejas_ni_las_exentas_seguro(self):
        """
        F6. Given ACTIVE de hace 40 días, una abierta el día del torneo y una normal
        When se buscan candidatas
        Then solo la normal
        """
        uow = InMemoryUnitOfWork()
        vieja = await _competicion(
            uow, abierta=ANTES - timedelta(days=60), inicio=HOY - timedelta(40)
        )
        exenta = await _competicion(uow, abierta=datetime.combine(TORNEO, time(0, 0), tzinfo=UTC))
        normal = await _competicion(uow)
        sin_fecha = await _competicion(uow)
        sin_fecha._enrollment_opened_at = None

        async with uow:
            candidatas = await uow.competitions.find_active_starting_by(
                HOY - timedelta(days=30), TORNEO
            )

        ids = {c.id for c in candidatas}
        assert normal.id in ids
        assert sin_fecha.id in ids
        assert vieja.id not in ids
        assert exenta.id not in ids

    async def test_el_cierre_mira_hasta_30_dias_atras(self):
        """F6. Given una ACTIVE que empezó hace 30 días, y otra hace 31 / Then solo la primera."""
        uow = InMemoryUnitOfWork()
        hace_30 = await _competicion(uow, abierta=ANTES - timedelta(60), inicio=HOY - timedelta(30))
        hace_31 = await _competicion(uow, abierta=ANTES - timedelta(60), inicio=HOY - timedelta(31))

        class _Cerrar:
            def __init__(self):
                self.pedidas = []

            async def cerrar_por_el_plazo(self, competition_id):
                self.pedidas.append(competition_id)

        cerrar = _Cerrar()
        # Un reloj fijo en HOY: con el de verdad, pasadas las 00:00 UTC las fechas
        # de arriba (calculadas al importar) quedarían un día más atrás (CodeRabbit)
        mediodia = datetime(HOY.year, HOY.month, HOY.day, 12, tzinfo=UTC)
        await CloseEnrollmentsPastDeadlineUseCase(
            uow, cerrar, PlazoDeInscripcion(_Zonas(), reloj=lambda: mediodia)
        ).execute()

        assert hace_30.id in cerrar.pedidas
        assert hace_31.id not in cerrar.pedidas


class TestF7LaProgramadaSeAbreASuHora:
    async def _organizador_e_invitado(self, user_uow):
        gente = []
        for _ in range(2):
            u = User.create(
                first_name="Ana",
                last_name="Plazo",
                email_str=f"ana-{uuid4().hex[:6]}@test.com",
                plain_password="SecureP@ssw0rd123",
                gender=Gender.FEMALE,
            )
            async with user_uow:
                await user_uow.users.save(u)
            gente.append(u)
        return gente

    async def test_invitar_a_una_que_ya_tocaba_no_la_exime(self):
        """
        F7. Given programada a 5 días, que ya debía estar abierta, y el plazo pasado
        When el organizador invita
        Then se abre a su hora programada, y el plazo no deja invitar
        """
        uow, user_uow = InMemoryUnitOfWork(), UserInMemoryUoW()
        organizador, invitado = await self._organizador_e_invitado(user_uow)
        competition = await _competicion(uow, abierta=None, dias=5)
        competition._creator_id = organizador.id
        programada = competition.scheduled_opening_at("Europe/Madrid")

        with pytest.raises(EnrollmentDeadlinePassedError):
            await SendInvitationByUserIdUseCase(uow, user_uow, plazo=_plazo(DESPUES)).execute(
                SendInvitationByUserIdRequestDTO(
                    competition_id=competition.id.value,
                    inviter_id=organizador.id.value,
                    invitee_user_id=invitado.id.value,
                )
            )

        assert competition.enrollment_opened_at == programada.astimezone(UTC).replace(tzinfo=None)

    async def test_invitar_a_una_que_todavia_no_tocaba_la_abre_ahora(self):
        """F7. Given programada a 14 días de un torneo lejano / When invita / Then abre ahora."""
        uow, user_uow = InMemoryUnitOfWork(), UserInMemoryUoW()
        organizador, invitado = await self._organizador_e_invitado(user_uow)
        competition = await _competicion(
            uow, abierta=None, dias=14, inicio=HOY + timedelta(days=60)
        )
        competition._creator_id = organizador.id
        antes = datetime.now(UTC).replace(tzinfo=None)

        await SendInvitationByUserIdUseCase(uow, user_uow, plazo=_plazo(DESPUES)).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=competition.id.value,
                inviter_id=organizador.id.value,
                invitee_user_id=invitado.id.value,
            )
        )

        assert competition.status is CompetitionStatus.ACTIVE
        assert competition.enrollment_opened_at >= antes

    async def test_activar_una_que_ya_tocaba_la_abre_ahora(self):
        """O3 (16 nov). Given programada que ya debía estar abierta / When se activa / Then ahora."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(uow, abierta=None, dias=5)
        antes = datetime.now(UTC).replace(tzinfo=None)

        respuesta = await ActivateCompetitionUseCase(uow).execute(
            ActivateCompetitionRequestDTO(competition_id=competition.id.value),
            competition.creator_id,
        )

        assert respuesta.status == "ACTIVE"
        assert competition.enrollment_opened_at >= antes

    async def test_activar_una_que_no_tocaba_la_abre_ahora(self):
        """F7. Given programada para dentro de mucho / When se activa / Then ahora."""
        uow = InMemoryUnitOfWork()
        competition = await _competicion(
            uow, abierta=None, dias=14, inicio=HOY + timedelta(days=60)
        )
        antes = datetime.now(UTC).replace(tzinfo=None)

        await ActivateCompetitionUseCase(uow).execute(
            ActivateCompetitionRequestDTO(competition_id=competition.id.value),
            competition.creator_id,
        )

        assert competition.status is CompetitionStatus.ACTIVE
        assert competition.enrollment_opened_at >= antes


class TestO1LasSalidasCambianDeDia:
    async def test_se_avisa_con_la_foto_de_antes_y_la_de_despues(self, monkeypatch):
        """
        O1. Given una sesión con salidas
        When se mueve el torneo
        Then se avisa de cada sesión con sus salidas de antes y de después (como al
        cambiar una ronda: quien publica compara y avisa del día nuevo)
        """
        from src.modules.competition.application.use_cases import update_competition_use_case

        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        ronda = await _sesion(uow, competition, TORNEO)
        fotos = iter([{"antes": 1}, {"despues": 2}])

        async def foto(_uow, round_id):
            assert round_id == ronda.id
            return next(fotos)

        monkeypatch.setattr(update_competition_use_case, "salidas_vigentes", foto)
        llamadas = []

        class _Salidas(_Avisos):
            async def salidas_cambiadas(self, competition, round_id, antes, despues):
                llamadas.append((round_id, antes, despues))

        avisos = _Salidas()
        caso = _mover(uow, avisos=None)
        caso._actividad = avisos

        await caso.execute(competition.id, _fechas(7), competition.creator_id)

        assert llamadas == [(ronda.id, {"antes": 1}, {"despues": 2})]


class TestF1LosPaisesAcompanantes:
    async def test_quitar_los_paises_acompanantes_es_un_cambio(self):
        """F1. Given cerrada por el plazo con Francia de acompañante / When llega `countries: []` / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        competition._location = Location(main_country="ES", adjacent_country_1="FR")

        with pytest.raises(CompetitionNotEditableError):
            await _mover(uow).execute(
                competition.id, _fechas(7, countries=[]), competition.creator_id
            )

    async def test_los_mismos_paises_no(self):
        """F1. Given con Francia / When llega `countries: ["FR"]` / Then se mueve."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        competition._location = Location(main_country="ES", adjacent_country_1="FR")

        await _mover(uow).execute(
            competition.id, _fechas(7, countries=["FR"]), competition.creator_id
        )

        assert competition.dates.start_date == TORNEO + timedelta(days=7)


class TestO1UnaSesionJugadaNoSeMueve:
    @pytest.mark.parametrize("estado", [RoundStatus.IN_PROGRESS, RoundStatus.COMPLETED])
    async def test_la_sesion_no_se_deja(self, estado):
        """O1. Given una sesión en juego o terminada / When se le mueven los días / Then no."""
        uow = InMemoryUnitOfWork()
        competition = await _cerrada_por_el_plazo(uow)
        ronda = await _sesion(uow, competition, TORNEO)
        ronda._status = estado

        with pytest.raises(ValueError):
            ronda.desplazar(3)

        assert ronda.round_date == TORNEO
