"""
Rehacer los sobres de una sesion (FE #655).

Cuando un capitan no llega a tiempo, la aplicacion rellena su sobre y salen los
enfrentamientos. Lo que viene despues **no es editar el resultado: es rehacer el
proceso**, y solo puede pedirlo el organizador —es quien arbitra, y el capitan
que si entrego a tiempo no se queda sin su lista por culpa del que se olvido—.

Se lleva los sobres Y los partidos de esa sesion, porque unos partidos que ya no
se parecen a ningun sobre son enfrentamientos inventados. Y solo mientras no se
haya jugado nada: se protege lo jugado, no lo montado.
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import (
    NotCompetitionCreatorError,
    RoundNotFoundError,
)
from src.modules.competition.application.use_cases.reset_envelopes_use_case import (
    NothingToResetError,
    ResetEnvelopesUseCase,
    SessionAlreadyPlayedError,
)
from src.modules.competition.application.use_cases.submit_envelope_use_case import (
    SubmitEnvelopeUseCase,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


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


async def _montar(jugadores: int = 4):
    """Una cerrada con equipos, dos capitanes y una sesion de individuales."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    comp_id = CompetitionId(creada.id)
    resto = [UserId(uuid4()) for _ in range(jugadores - 1)]
    for jugador in resto:
        await create_approved_enrollment(uow, creada.id, jugador)
    await set_competition_status(uow, creada.id, "CLOSED")

    todos = [creator_id, *resto]
    mitad = len(todos) // 2
    equipo_a, equipo_b = todos[:mitad], todos[mitad:]
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.name_captains(equipo_a[0], equipo_b[0], todos, has_teams=False)
        await uow.competitions.update(competicion)
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
        ronda.mark_teams_assigned()
        await uow.rounds.add(ronda)
        await uow.commit()
    return uow, comp_id, ronda.id, equipo_a, equipo_b


def _jugador_de_partido(user_id):
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )


async def _generar_partidos(uow, round_id, equipo_a, equipo_b):
    """Deja la sesion como queda tras generar sus partidos."""
    creados = []
    async with uow:
        for i, (a, b) in enumerate(zip(equipo_a, equipo_b, strict=False), start=1):
            partido = Match.create(
                round_id=round_id,
                match_number=i,
                team_a_players=[_jugador_de_partido(a)],
                team_b_players=[_jugador_de_partido(b)],
            )
            await uow.matches.add(partido)
            creados.append(partido)
        ronda = await uow.rounds.find_by_id(round_id)
        ronda.mark_matches_generated()
        await uow.rounds.update(ronda)
        await uow.commit()
    return creados


async def _entregar_los_dos(uow, round_id, equipo_a, equipo_b):
    entregar = SubmitEnvelopeUseCase(uow, _RepoUsuarios())
    for capitan, equipo in ((equipo_a[0], equipo_a), (equipo_b[0], equipo_b)):
        await entregar.execute(round_id.value, capitan, [[str(uid.value)] for uid in equipo])


def _resetear(uow):
    return ResetEnvelopesUseCase(uow, _RepoUsuarios())


class TestRehacerLosSobres:
    async def test_se_van_los_sobres_y_los_partidos_y_la_sesion_vuelve_a_esperarlos(self):
        """Rehacer el proceso entero, que es de lo que se trata."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)
        await _generar_partidos(uow, round_id, equipo_a, equipo_b)

        respuesta = await _resetear(uow).execute(round_id.value, equipo_a[0])

        async with uow:
            assert await uow.envelopes.find_by_round(round_id) == []
            assert await uow.matches.find_by_round(round_id) == []
            ronda = await uow.rounds.find_by_id(round_id)
            assert ronda.status == RoundStatus.PENDING_MATCHES
        assert respuesta.envelopes_removed == 2
        assert respuesta.matches_removed == len(equipo_a)

    async def test_y_los_capitanes_pueden_volver_a_entregar(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)
        await _resetear(uow).execute(round_id.value, equipo_a[0])

        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)

        async with uow:
            sobres = await uow.envelopes.find_by_round(round_id)
        assert len(sobres) == 2
        assert all(sobre.is_sealed() for sobre in sobres)

    async def test_sin_partidos_generados_tambien_vale(self):
        """Los capitanes se equivocaron y todavia no se ha generado nada."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)

        respuesta = await _resetear(uow).execute(round_id.value, equipo_a[0])

        assert respuesta.envelopes_removed == 2
        assert respuesta.matches_removed == 0

    async def test_un_administrador_tambien(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)

        respuesta = await _resetear(uow).execute(round_id.value, UserId(uuid4()), is_admin=True)

        assert respuesta.envelopes_removed == 2


class TestQuienNoPuede:
    async def test_un_capitan_no_rehace_el_proceso(self):
        """El que entrego a tiempo no se queda sin su lista por el otro."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)

        with pytest.raises(NotCompetitionCreatorError):
            await _resetear(uow).execute(round_id.value, equipo_b[0])

    async def test_ni_un_jugador_cualquiera(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)

        with pytest.raises(NotCompetitionCreatorError):
            await _resetear(uow).execute(round_id.value, equipo_a[1])

    async def test_una_sesion_que_no_existe(self):
        uow, _, _, equipo_a, _ = await _montar()

        with pytest.raises(RoundNotFoundError):
            await _resetear(uow).execute(uuid4(), equipo_a[0])


class TestLoJugadoNoSeToca:
    async def test_con_un_partido_terminado_no_se_rehace(self):
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)
        partidos = await _generar_partidos(uow, round_id, equipo_a, equipo_b)
        async with uow:
            partido = await uow.matches.find_by_id(partidos[0].id)
            partido.start()
            partido.concede(conceding_team="B")
            await uow.matches.update(partido)
            await uow.commit()

        with pytest.raises(SessionAlreadyPlayedError):
            await _resetear(uow).execute(round_id.value, equipo_a[0])

    async def test_y_los_sobres_siguen_donde_estaban(self):
        """Un rechazo no puede dejarse la mitad hecha por el camino."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)
        partidos = await _generar_partidos(uow, round_id, equipo_a, equipo_b)
        async with uow:
            partido = await uow.matches.find_by_id(partidos[0].id)
            partido.start()
            partido.concede(conceding_team="B")
            await uow.matches.update(partido)
            await uow.commit()

        with pytest.raises(SessionAlreadyPlayedError):
            await _resetear(uow).execute(round_id.value, equipo_a[0])

        async with uow:
            assert len(await uow.envelopes.find_by_round(round_id)) == 2
            assert len(await uow.matches.find_by_round(round_id)) == len(partidos)

    async def test_un_partido_empezado_sin_anotar_nada_no_estorba(self):
        """Se protege lo jugado, no lo montado: la anotacion se abre sola."""
        uow, _, round_id, equipo_a, equipo_b = await _montar()
        await _entregar_los_dos(uow, round_id, equipo_a, equipo_b)
        partidos = await _generar_partidos(uow, round_id, equipo_a, equipo_b)
        async with uow:
            partido = await uow.matches.find_by_id(partidos[0].id)
            partido.start()
            await uow.matches.update(partido)
            await uow.commit()

        respuesta = await _resetear(uow).execute(round_id.value, equipo_a[0])

        assert respuesta.matches_removed == len(partidos)


class TestCuandoNoHayNadaQueRehacer:
    async def test_sin_sobres_ni_partidos_se_dice(self):
        """Ofrecerlo seria mandar al organizador contra un boton que no hace nada."""
        uow, _, round_id, equipo_a, _ = await _montar()

        with pytest.raises(NothingToResetError):
            await _resetear(uow).execute(round_id.value, equipo_a[0])
