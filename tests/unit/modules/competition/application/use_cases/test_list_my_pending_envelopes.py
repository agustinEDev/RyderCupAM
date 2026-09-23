"""
Los sobres que me faltan por entregar (FE #655).

Un capitan no puede enterarse de que tiene un sobre pendiente entrando sesion
por sesion en la agenda de cada competicion: sin esto, el plazo le vence sin
saberlo y la aplicacion rellena su lista por handicap. Aqui salen los suyos,
para el bloque «Requiere tu Atencion» del panel.

Solo lo que se puede hacer AHORA: un sobre ya entregado, uno ya abierto o una
sesion con los partidos hechos no son nada que atender.
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.use_cases.list_my_pending_envelopes_use_case import (
    ListMyPendingEnvelopesUseCase,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    SubmitEnvelopeUseCase,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio

# La sesion del montaje es del 1 de junio
_ANTES = date(2026, 5, 20)
_DESPUES = date(2026, 6, 5)


class _RepoUsuarios:
    """Lo justo que pide la mesa de sobres."""

    class _Usuario:
        def __init__(self, user_id):
            self.id = user_id
            self.handicap = None

        def display_name_or_legal(self, nombre_legal: bool) -> str:
            return "Jugador"

    async def find_by_id(self, user_id):
        return self._Usuario(user_id)

    async def find_by_ids(self, user_ids):
        return [self._Usuario(uid) for uid in user_ids]


class _Calendario:
    """El dia de hoy segun el servidor, que en los tests se mueve a mano."""

    def __init__(self, hoy: date):
        self._hoy = hoy

    def __call__(self) -> date:
        return self._hoy


async def _montar(con_equipos: bool = True):
    """Una cerrada con equipos, sus capitanes y una sesion del 1 de junio."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    comp_id = CompetitionId(creada.id)
    resto = [UserId(uuid4()) for _ in range(3)]
    for jugador in resto:
        await create_approved_enrollment(uow, creada.id, jugador)
    await set_competition_status(uow, creada.id, "CLOSED")

    todos = [creator_id, *resto]
    equipo_a, equipo_b = todos[:2], todos[2:]
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.name_captains(equipo_a[0], equipo_b[0], todos, has_teams=False)
        await uow.competitions.update(competicion)
        if con_equipos:
            await uow.team_assignments.add(
                TeamAssignment.create(
                    competition_id=comp_id,
                    team_a_player_ids=equipo_a,
                    team_b_player_ids=equipo_b,
                    mode=TeamAssignmentMode.DRAFT,
                )
            )
        ronda = Round.create(
            competition_id=comp_id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        if con_equipos:
            ronda.mark_teams_assigned()
        await uow.rounds.add(ronda)
        await uow.commit()
    return uow, comp_id, ronda.id, equipo_a, equipo_b


def _pendientes(uow, hoy: date = _ANTES):
    return ListMyPendingEnvelopesUseCase(uow, _Calendario(hoy))


async def _entregar(uow, round_id, capitan, equipo):
    await SubmitEnvelopeUseCase(uow, _RepoUsuarios()).execute(
        round_id.value, capitan, [[str(uid.value)] for uid in equipo]
    )


class TestLoQueMeFaltaPorEntregar:
    async def test_un_capitan_ve_su_sobre_pendiente(self):
        uow, _, round_id, equipo_a, _ = await _montar()

        pendientes = await _pendientes(uow).execute(equipo_a[0])

        assert [p.round_id for p in pendientes] == [round_id.value]

    async def test_con_los_datos_para_pintarlo(self):
        """El panel no va a pedir la competición aparte por cada aviso."""
        uow, comp_id, _, equipo_a, _ = await _montar()

        (pendiente,) = await _pendientes(uow).execute(equipo_a[0])

        assert pendiente.competition_id == comp_id.value
        assert pendiente.competition_name
        assert pendiente.round_date == date(2026, 6, 1)
        assert pendiente.session_type == "MORNING"

    async def test_los_dos_capitanes_tienen_el_suyo(self):
        uow, _, _, equipo_a, equipo_b = await _montar()

        assert len(await _pendientes(uow).execute(equipo_a[0])) == 1
        assert len(await _pendientes(uow).execute(equipo_b[0])) == 1

    async def test_y_al_entregarlo_desaparece(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        await _entregar(uow, round_id, equipo_a[0], equipo_a)

        assert await _pendientes(uow).execute(equipo_a[0]) == []

    async def test_pero_el_del_rival_sigue_pendiente(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar(uow, round_id, equipo_a[0], equipo_a)

        assert len(await _pendientes(uow).execute(equipo_b[0])) == 1


class TestLoQueNoEsNadaQueAtender:
    async def test_quien_no_capitanea_no_tiene_sobres(self):
        uow, _, _, equipo_a, _ = await _montar()

        assert await _pendientes(uow).execute(equipo_a[1]) == []

    async def test_un_ajeno_a_todo_tampoco(self):
        uow, _, _, _, _ = await _montar()

        assert await _pendientes(uow).execute(UserId(uuid4())) == []

    async def test_una_sesion_que_ya_paso(self):
        """Su plazo venció: la aplicación ya rellenó lo que faltara."""
        uow, _, _, equipo_a, _ = await _montar()

        assert await _pendientes(uow, hoy=_DESPUES).execute(equipo_a[0]) == []

    async def test_el_dia_de_la_sesion_todavia_cuenta(self):
        """Hasta que se abren, el capitán puede corregir su lista."""
        uow, _, _, equipo_a, _ = await _montar()

        assert len(await _pendientes(uow, hoy=date(2026, 6, 1)).execute(equipo_a[0])) == 1

    async def test_una_sesion_con_los_partidos_ya_hechos(self):
        uow, _, round_id, equipo_a, _ = await _montar()
        async with uow:
            ronda = await uow.rounds.find_by_id(round_id)
            ronda.mark_matches_generated()
            await uow.rounds.update(ronda)
            await uow.commit()

        assert await _pendientes(uow).execute(equipo_a[0]) == []

    async def test_unos_sobres_ya_abiertos_aunque_no_haya_partidos(self):
        """Al vencer el plazo se abren solos y la sesión sigue esperando partidos.

        Avisar ahí manda al capitán a una pantalla donde ya no puede hacer
        nada: su lista la puso la aplicación y no se toca.
        """
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar(uow, round_id, equipo_b[0], equipo_b)
        async with uow:
            for sobre in await uow.envelopes.find_by_round(round_id):
                if sobre.is_submitted():
                    sobre.reveal()
                    await uow.envelopes.update(sobre)
            await uow.commit()

        assert await _pendientes(uow).execute(equipo_a[0]) == []

    async def test_una_competicion_sin_equipos_repartidos(self):
        """Sin equipos no hay sobre que entregar: primero se reparten."""
        uow, _, _, equipo_a, _ = await _montar(con_equipos=False)

        assert await _pendientes(uow).execute(equipo_a[0]) == []
