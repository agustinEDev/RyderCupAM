"""
El cierre de inscripciones por el plazo, cada hora (15 nov 2026).

| Caso | Situación                                              | Qué pasa                                     |
|------|--------------------------------------------------------|----------------------------------------------|
| C3   | ACTIVE abierta antes, pasado el plazo                  | CLOSED con el MISMO caso de uso, por el plazo |
| C3   | antes del plazo, en borrador, ya cerrada               | no se toca                                    |
| C3   | Medal con todos con hándicap                           | se cierra y fija hándicaps, como a mano       |
| C3   | una que falla no para las demás                        | las demás se cierran                          |
| C3   | solo se miran las que empiezan como mucho en dos días  | las de dentro de un mes, ni se leen           |
| C3   | cerrar a mano                                          | no queda «por el plazo» ni se avisa           |
| C4   | Medal con alguien sin hándicap (o sin franja)          | sigue ACTIVE y UN aviso al organizador        |
| C4   | la vuelta siguiente, igual                             | sin otro aviso                                |
| C4   | lo arregla                                             | la vuelta siguiente la cierra                 |
| C5   | cerrada por el plazo                                   | «Se han cerrado las inscripciones de X»       |
| R1   | reabierta pasado el plazo                              | el cierre no la toca                          |
| R3   | movida más tarde, plazo nuevo en el futuro             | no se cierra hasta el plazo nuevo             |
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.ports.competition_activity_publisher_interface import (
    CloseBlockedReason,
)
from src.modules.competition.application.services.franjas_al_cerrar import (
    PlayersWithoutTeeWindowError,
)
from src.modules.competition.application.services.handicaps_al_cerrar import (
    PlayersWithoutHandicapError,
)
from src.modules.competition.application.services.plazo_de_inscripcion import (
    PlazoDeInscripcion,
)
from src.modules.competition.application.use_cases.close_enrollments_past_deadline_use_case import (
    CloseEnrollmentsPastDeadlineUseCase,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    plaza_para_todos,
)

pytestmark = pytest.mark.asyncio

TORNEO = date(2026, 11, 20)
# Las 12:00 de Madrid del 19 de noviembre son las 11:00 UTC
PLAZO = datetime(2026, 11, 19, 11, 0, tzinfo=UTC)
ANTES = PLAZO - timedelta(days=5)
DESPUES = PLAZO + timedelta(hours=1)


class _Zonas:
    async def for_competition(self, competition):
        return "Europe/Madrid"

    async def for_course(self, golf_course_id):
        return "Europe/Madrid"


class _Avisos:
    """El puerto de Actividad, apuntando lo que interesa aquí."""

    def __init__(self):
        self.avisos: list[tuple] = []

    async def enrollments_closed(self, competition):
        self.avisos.append(("closed", competition.id))

    async def close_blocked(self, competition, reason, players):
        self.avisos.append(("blocked", competition.id, reason, players))

    def __getattr__(self, _nombre):
        async def nada(*_args, **_kwargs):
            return None

        return nada


class _Usuarios:
    """Con hándicap, salvo los que se digan."""

    def __init__(self):
        self.sin_handicap: set[UserId] = set()

    def _usuario(self, user_id):
        u = MagicMock()
        u.id = user_id
        u.handicap = None if user_id in self.sin_handicap else MagicMock(value=Decimal("10.0"))
        u.display_name_or_legal.return_value = "Nombre"
        u.get_public_name.return_value = "Nombre"
        u.get_full_name.return_value = "Nombre"
        return u

    async def find_by_ids(self, ids):
        return [self._usuario(i) for i in ids]

    async def find_by_id(self, user_id):
        return self._usuario(user_id)


def _bloqueado() -> SimpleNamespace:
    return SimpleNamespace(user_id=UserId.generate(), name="Ana")


class _Escenario:
    def __init__(self, ahora: datetime = DESPUES):
        self.uow = InMemoryUnitOfWork()
        self.usuarios = _Usuarios()
        self.avisos = _Avisos()
        self.ahora = ahora

    @property
    def plazo(self) -> PlazoDeInscripcion:
        return PlazoDeInscripcion(_Zonas(), reloj=lambda: self.ahora)

    def cerrar(self) -> CloseEnrollmentsUseCase:
        return CloseEnrollmentsUseCase(
            self.uow, self.usuarios, actividad=self.avisos, plazo=self.plazo
        )

    def cierre(self, cerrar=None) -> CloseEnrollmentsPastDeadlineUseCase:
        return CloseEnrollmentsPastDeadlineUseCase(
            self.uow, cerrar or self.cerrar(), self.plazo, actividad=self.avisos
        )

    async def ryder(self, abierta: datetime = ANTES, inicio: date = TORNEO) -> Competition:
        competition = Competition.create(
            id=CompetitionId.generate(),
            creator_id=UserId.generate(),
            name=CompetitionName(f"Copa {uuid4().hex[:6]}"),
            dates=DateRange(inicio, inicio + timedelta(days=1)),
            location=Location(main_country="ES"),
            team_1_name="Europa",
            team_2_name="USA",
            play_mode=PlayMode.SCRATCH,
        )
        competition.activate(now=abierta)
        async with self.uow:
            await self.uow.competitions.add(competition)
        return competition

    async def medal(self, sin_handicap: int = 0) -> Competition:
        respuesta = await CreateCompetitionUseCase(
            self.uow, LocationBuilder(self.uow.countries), USUARIOS_CON_GENERO
        ).execute(
            CreateCompetitionRequestDTO(
                name=f"Medal {uuid4().hex[:6]}",
                start_date=TORNEO,
                end_date=TORNEO,
                main_country="ES",
                play_mode="HANDICAP",
                tournament_type="MEDAL",
                stroke_play={"category_limits": [Decimal("12.0")]},
            ),
            UserId.generate(),
        )
        async with self.uow:
            competition = await self.uow.competitions.find_by_id(CompetitionId(respuesta.id))
            competition._enrollment_opened_at = ANTES.replace(tzinfo=None)
            for i in range(sin_handicap + 1):
                jugador = UserId.generate()
                if i < sin_handicap:
                    self.usuarios.sin_handicap.add(jugador)
                await self.uow.enrollments.add(
                    Enrollment.direct_enroll(
                        id=EnrollmentId.generate(),
                        competition_id=competition.id,
                        user_id=jugador,
                    )
                )
        await plaza_para_todos(self.uow, competition.id)
        return competition

    async def estado(self, competition: Competition) -> Competition:
        async with self.uow:
            return await self.uow.competitions.find_by_id(competition.id)


class TestCierraLasQueLesToca:
    async def test_pasado_el_plazo_se_cierra_por_el_plazo_y_se_avisa(self):
        """
        C3, C5. Given una Ryder ACTIVE abierta antes del plazo
        When pasa la vuelta pasado el plazo
        Then queda CLOSED, cerrada por el plazo, y el organizador recibe el aviso
        """
        escenario = _Escenario()
        competition = await escenario.ryder()

        resumen = await escenario.cierre().execute()

        cerrada = await escenario.estado(competition)
        assert cerrada.status is CompetitionStatus.CLOSED
        assert cerrada.enrollment_closed_by_deadline is True
        assert resumen.closed == 1
        assert ("closed", competition.id) in escenario.avisos.avisos

    async def test_antes_del_plazo_no(self):
        """C3. Given la misma / When la vuelta es antes del plazo / Then sigue ACTIVE, sin aviso."""
        escenario = _Escenario(ahora=PLAZO - timedelta(minutes=1))
        competition = await escenario.ryder()

        resumen = await escenario.cierre().execute()

        assert (await escenario.estado(competition)).status is CompetitionStatus.ACTIVE
        assert resumen.closed == 0
        assert escenario.avisos.avisos == []

    async def test_reabierta_pasado_el_plazo_no(self):
        """R1. Given abierta (o reabierta) pasado el plazo / Then la vuelta no la toca."""
        escenario = _Escenario(ahora=DESPUES + timedelta(days=1))
        competition = await escenario.ryder(abierta=DESPUES)

        await escenario.cierre().execute()

        assert (await escenario.estado(competition)).status is CompetitionStatus.ACTIVE

    async def test_movida_mas_tarde_espera_al_plazo_nuevo(self):
        """
        R3. Given reabierta tarde y movida una semana más tarde
        When pasa la vuelta antes del plazo nuevo, y luego después
        Then primero sigue abierta, y luego se cierra
        """
        escenario = _Escenario()
        competition = await escenario.ryder(abierta=DESPUES)
        async with escenario.uow:
            movida = await escenario.uow.competitions.find_by_id(competition.id)
            nuevo = TORNEO + timedelta(days=7)
            movida.update_info(dates=DateRange(nuevo, nuevo + timedelta(days=1)))

        escenario.ahora = PLAZO + timedelta(days=6)
        await escenario.cierre().execute()
        assert (await escenario.estado(competition)).status is CompetitionStatus.ACTIVE

        escenario.ahora = PLAZO + timedelta(days=7, minutes=1)
        await escenario.cierre().execute()
        assert (await escenario.estado(competition)).status is CompetitionStatus.CLOSED

    async def test_solo_mira_las_que_empiezan_en_dos_dias_como_mucho(self):
        """
        C3. Given la vuelta del 19 y ACTIVE que empiezan el 20, el 21, el 22 y en un mes
        When pasa la vuelta
        Then solo se intentan cerrar las de hasta el 21: el plazo de las demás no ha
        podido pasar en ninguna zona
        """
        escenario = _Escenario()
        del_20 = await escenario.ryder()
        del_21 = await escenario.ryder(inicio=TORNEO + timedelta(days=1))
        del_22 = await escenario.ryder(inicio=TORNEO + timedelta(days=2))
        lejana = await escenario.ryder(inicio=TORNEO + timedelta(days=30))

        class _Cerrar:
            def __init__(self):
                self.pedidas: list[CompetitionId] = []

            async def cerrar_por_el_plazo(self, competition_id):
                self.pedidas.append(competition_id)

        cerrar = _Cerrar()
        await escenario.cierre(cerrar).execute()

        assert set(cerrar.pedidas) == {del_20.id, del_21.id}
        assert del_22.id not in cerrar.pedidas
        assert lejana.id not in cerrar.pedidas

    async def test_una_que_falla_no_para_las_demas(self):
        """C3. Given dos, y cerrar la primera revienta / Then la segunda se cierra igual."""
        escenario = _Escenario()
        primera = await escenario.ryder()
        segunda = await escenario.ryder()
        de_verdad = escenario.cerrar()

        class _Cerrar:
            async def cerrar_por_el_plazo(self, competition_id):
                if competition_id == primera.id:
                    raise RuntimeError("se cayó la base")
                return await de_verdad.cerrar_por_el_plazo(competition_id)

        resumen = await escenario.cierre(_Cerrar()).execute()

        assert (await escenario.estado(segunda)).status is CompetitionStatus.CLOSED
        assert resumen.closed == 1
        assert resumen.failed == 1

    async def test_un_medal_se_cierra_como_a_mano(self):
        """C3. Given un Medal con todos con hándicap / Then cerrado y con su hándicap fijado."""
        escenario = _Escenario()
        competition = await escenario.medal()

        await escenario.cierre().execute()

        assert (await escenario.estado(competition)).status is CompetitionStatus.CLOSED
        async with escenario.uow:
            inscritos = await escenario.uow.enrollments.find_by_competition(competition.id)
        assert all(e.fixed_handicap is not None for e in inscritos)


class TestCerrarAMano:
    async def test_no_queda_por_el_plazo_ni_se_avisa(self):
        """C3, C5. Given ACTIVE / When la cierra el organizador / Then a mano y sin aviso de C5."""
        escenario = _Escenario()
        competition = await escenario.ryder()

        await escenario.cerrar().execute(
            CloseEnrollmentsRequestDTO(competition_id=competition.id.value),
            competition.creator_id,
        )

        cerrada = await escenario.estado(competition)
        assert cerrada.status is CompetitionStatus.CLOSED
        assert cerrada.enrollment_closed_by_deadline is False
        assert ("closed", competition.id) not in escenario.avisos.avisos

    async def test_por_el_plazo_sin_plazo_no_se_puede(self):
        """C3. Given el caso de uso sin plazo / When se le pide cerrar por el plazo / Then error."""
        escenario = _Escenario()
        competition = await escenario.ryder()

        with pytest.raises(RuntimeError):
            await CloseEnrollmentsUseCase(escenario.uow, escenario.usuarios).cerrar_por_el_plazo(
                competition.id
            )

    async def test_por_el_plazo_una_que_no_existe_no_hace_nada(self):
        """C3. Given un id que ya no existe (borrada entre medias) / Then None, sin error."""
        escenario = _Escenario()

        assert await escenario.cerrar().cerrar_por_el_plazo(CompetitionId.generate()) is None


class TestLaQueNoSePuedeCerrar:
    async def test_sigue_abierta_y_se_avisa_una_vez(self):
        """
        C4. Given un Medal con dos inscritos sin hándicap
        When pasan dos vueltas pasado el plazo
        Then sigue ACTIVE, y el organizador recibe UN aviso con el motivo y cuántos
        """
        escenario = _Escenario()
        competition = await escenario.medal(sin_handicap=2)

        primera = await escenario.cierre().execute()
        segunda = await escenario.cierre().execute()

        sigue = await escenario.estado(competition)
        assert sigue.status is CompetitionStatus.ACTIVE
        assert sigue.close_blocked_notified is True
        assert escenario.avisos.avisos == [
            ("blocked", competition.id, CloseBlockedReason.NO_HANDICAP, 2)
        ]
        assert (primera.blocked, primera.notified) == (1, 1)
        assert (segunda.blocked, segunda.notified) == (1, 0)

    async def test_sin_franja_el_motivo_es_ese(self):
        """C4. Given cerrarla falla por jugadores sin franja / Then el aviso dice sin franja."""
        escenario = _Escenario()
        competition = await escenario.ryder()

        class _Cerrar:
            async def cerrar_por_el_plazo(self, competition_id):
                raise PlayersWithoutTeeWindowError([_bloqueado(), _bloqueado(), _bloqueado()])

        await escenario.cierre(_Cerrar()).execute()

        assert escenario.avisos.avisos == [
            ("blocked", competition.id, CloseBlockedReason.NO_TEE_WINDOW, 3)
        ]

    async def test_sin_handicap_por_el_error_tambien(self):
        """C4. Given cerrarla falla por hándicap / Then el motivo es el hándicap."""
        escenario = _Escenario()
        competition = await escenario.ryder()

        class _Cerrar:
            async def cerrar_por_el_plazo(self, competition_id):
                raise PlayersWithoutHandicapError([_bloqueado()])

        await escenario.cierre(_Cerrar()).execute()

        assert escenario.avisos.avisos == [
            ("blocked", competition.id, CloseBlockedReason.NO_HANDICAP, 1)
        ]

    async def test_si_ya_no_esta_abierta_no_se_avisa(self):
        """C4. Given bloqueada pero cerrada a mano entre medias / Then no se avisa."""
        escenario = _Escenario()
        await escenario.ryder()

        class _Cerrar:
            async def cerrar_por_el_plazo(self, competition_id):
                async with escenario.uow:
                    cerrada = await escenario.uow.competitions.find_by_id(competition_id)
                    cerrada.close_enrollments()
                raise PlayersWithoutHandicapError([_bloqueado()])

        resumen = await escenario.cierre(_Cerrar()).execute()

        assert escenario.avisos.avisos == []
        assert resumen.notified == 0

    async def test_arreglado_la_vuelta_siguiente_la_cierra(self):
        """
        C4. Given bloqueada y avisada
        When el organizador lo arregla y pasa otra vuelta
        Then se cierra, avisa del cierre y el apunte del aviso se olvida
        """
        escenario = _Escenario()
        competition = await escenario.medal(sin_handicap=1)
        await escenario.cierre().execute()

        escenario.usuarios.sin_handicap.clear()
        resumen = await escenario.cierre().execute()

        cerrada = await escenario.estado(competition)
        assert cerrada.status is CompetitionStatus.CLOSED
        assert cerrada.close_blocked_notified is False
        assert resumen.closed == 1
        assert ("closed", competition.id) in escenario.avisos.avisos


class _Roto:
    """El feed caído: cualquier aviso revienta."""

    def __getattr__(self, _nombre):
        async def falla(*_args, **_kwargs):
            raise RuntimeError("feed caído")

        return falla


class TestSiFallaElAviso:
    async def test_cerrada_sigue_cerrada(self):
        """C5. Given el feed caído / When el plazo la cierra / Then queda cerrada igual."""
        escenario = _Escenario()
        escenario.avisos = _Roto()
        competition = await escenario.ryder()

        resumen = await escenario.cierre().execute()

        assert (await escenario.estado(competition)).status is CompetitionStatus.CLOSED
        assert resumen.closed == 1

    async def test_bloqueada_no_queda_apuntada_si_no_se_pudo_avisar(self):
        """C4/F3 (16 nov). Given el feed caído / When no se puede cerrar / Then sin apuntar."""
        escenario = _Escenario()
        escenario.avisos = _Roto()
        competition = await escenario.medal(sin_handicap=1)

        await escenario.cierre().execute()

        assert (await escenario.estado(competition)).close_blocked_notified is False
