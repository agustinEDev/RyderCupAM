"""
Deshacer los equipos cuando un jugador sale (release social 2, decidido el 27 oct 2026).

Con los equipos formados y sin partidos, quitar a un jugador (o que se retire)
dejaba los equipos descompensados, y al generar partidos se emparejaba
`min(a, b)`: uno se quedaba sin jugar y nadie avisaba. Se deshace el reparto y
se vuelve a como estaba antes de formar los equipos:

| Qué                                   | Queda                                      |
|---------------------------------------|--------------------------------------------|
| El reparto                            | Borrado                                    |
| Subcapitanes                          | Fuera (se eligen dentro de cada equipo)    |
| Capitanes                             | Se quedan (se nombran antes de repartir)   |
| Sala de draft                         | Borrada: se puede volver a abrir           |
| Sesiones esperando partidos           | Esperando equipos, sin bloqueo             |
| Sobres                                | Borrados (llevaban el reparto viejo)       |
| Con partidos ya generados             | No se deshace nada                         |
| Sin reparto                           | Nada que deshacer                          |
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.services.team_assignment_writer import (
    TeamAssignmentWriter,
)
from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.match_generation_block import (
    UNEXPECTED,
    MatchGenerationBlock,
)
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
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio


async def _montar(*, con_bloqueo: bool = False):
    """Una cerrada con equipos de dos, capitanes, subcapitanes, draft, sesión y sobre."""
    uow = InMemoryUnitOfWork()
    creador = UserId(uuid4())
    creada = await create_competition(uow, creador)
    comp_id = CompetitionId(creada.id)
    resto = [UserId(uuid4()) for _ in range(3)]
    for jugador in resto:
        await create_approved_enrollment(uow, creada.id, jugador)
    await set_competition_status(uow, creada.id, "CLOSED")
    todos = [creador, *resto]
    equipo_a, equipo_b = todos[:2], todos[2:]
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.name_captains(equipo_a[0], equipo_b[0], todos, has_teams=False)
        competicion.name_vice_captain("A", equipo_a[1], equipo_a, has_teams=True)
        await uow.competitions.update(competicion)
        await uow.team_assignments.add(
            TeamAssignment.create(
                competition_id=comp_id,
                team_a_player_ids=equipo_a,
                team_b_player_ids=equipo_b,
                mode=TeamAssignmentMode.DRAFT,
            )
        )
        await uow.drafts.add(Draft.create(comp_id, equipo_a[0], equipo_b[0]))
        ronda = Round.create(
            competition_id=comp_id,
            golf_course_id=GolfCourseId.generate(),
            round_date=date(2026, 12, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        ronda.mark_teams_assigned()
        if con_bloqueo:
            ronda.block_match_generation(MatchGenerationBlock(reason=UNEXPECTED))
        await uow.rounds.add(ronda)
        await uow.envelopes.add(Envelope.create(comp_id, ronda.id, "A", MatchFormat.SINGLES))
        await uow.commit()
    return uow, comp_id, ronda.id, equipo_a, equipo_b


async def _deshace(uow, comp_id) -> bool:
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        hecho = await TeamAssignmentWriter.deshacer(uow, competicion)
        await uow.commit()
    return hecho


async def test_sin_partidos_vuelve_a_antes_de_formar_los_equipos():
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()

    assert await _deshace(uow, comp_id) is True

    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        assert await uow.team_assignments.find_by_competition(comp_id) is None
        assert await uow.drafts.find_by_competition(comp_id) is None
        assert await uow.envelopes.find_by_round(round_id) == []
        ronda = await uow.rounds.find_by_id(round_id)
    assert competicion.ryder_cup.team_a_vice_captain_id is None
    assert competicion.ryder_cup.team_a_captain_id == equipo_a[0]
    assert competicion.ryder_cup.team_b_captain_id == equipo_b[0]
    assert ronda.status == RoundStatus.PENDING_TEAMS


async def test_la_sesion_bloqueada_tambien_vuelve_y_sin_el_bloqueo():
    uow, comp_id, round_id, _, _ = await _montar(con_bloqueo=True)

    await _deshace(uow, comp_id)

    async with uow:
        ronda = await uow.rounds.find_by_id(round_id)
    assert ronda.status == RoundStatus.PENDING_TEAMS
    assert ronda.match_generation_block is None


async def test_con_partidos_generados_no_se_deshace_nada():
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    async with uow:
        await uow.matches.add(
            Match.create(
                round_id=round_id,
                match_number=1,
                team_a_players=[_jugador(equipo_a[0])],
                team_b_players=[_jugador(equipo_b[0])],
            )
        )
        ronda = await uow.rounds.find_by_id(round_id)
        ronda.mark_matches_generated()
        await uow.rounds.update(ronda)
        await uow.commit()

    assert await _deshace(uow, comp_id) is False

    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is not None
        assert await uow.drafts.find_by_competition(comp_id) is not None
        competicion = await uow.competitions.find_by_id(comp_id)
    assert competicion.ryder_cup.team_a_vice_captain_id is not None


async def test_con_partidos_en_una_sesion_aun_esperandolos_tampoco():
    """Por si acaso: el estado de la sesión no basta, se miran los partidos."""
    uow, comp_id, round_id, equipo_a, equipo_b = await _montar()
    async with uow:
        await uow.matches.add(
            Match.create(
                round_id=round_id,
                match_number=1,
                team_a_players=[_jugador(equipo_a[0])],
                team_b_players=[_jugador(equipo_b[0])],
            )
        )
        await uow.commit()

    assert await _deshace(uow, comp_id) is False
    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is not None


async def test_en_juego_no_se_deshace():
    uow, comp_id, _, _, _ = await _montar()
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion.start()
        await uow.competitions.update(competicion)
        await uow.commit()

    assert await _deshace(uow, comp_id) is False
    async with uow:
        assert await uow.team_assignments.find_by_competition(comp_id) is not None


async def test_sin_la_pieza_de_la_ryder_no_se_toca_nada():
    """Un reparto sin Ryder no deberia existir; si existe, la baja no revienta (revisor)."""
    uow, comp_id, _, _, _ = await _montar()
    async with uow:
        competicion = await uow.competitions.find_by_id(comp_id)
        competicion._ryder_cup = None
        await uow.competitions.update(competicion)
        await uow.commit()

    assert await _deshace(uow, comp_id) is False


async def test_sin_reparto_no_hay_nada_que_deshacer():
    uow = InMemoryUnitOfWork()
    creada = await create_competition(uow, UserId(uuid4()))

    assert await _deshace(uow, CompetitionId(creada.id)) is False


def _jugador(user_id):
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )


async def test_una_sesion_ya_generada_aunque_sin_partidos_tampoco():
    uow, comp_id, round_id, _, _ = await _montar()
    async with uow:
        ronda = await uow.rounds.find_by_id(round_id)
        ronda.mark_matches_generated()
        await uow.rounds.update(ronda)
        await uow.commit()

    assert await _deshace(uow, comp_id) is False


async def test_la_sesion_solo_vuelve_a_esperar_equipos_si_esperaba_partidos():
    ronda = Round.create(
        competition_id=CompetitionId.generate(),
        golf_course_id=GolfCourseId.generate(),
        round_date=date(2026, 12, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )

    with pytest.raises(ValueError):
        ronda.mark_teams_unassigned()
