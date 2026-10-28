"""
Una Ryder cerrada con los equipos formados, para los tests de entrar y salir con
equipos (antes en test_deshacer_equipos, que probaba deshacerlos: desde la
release social 3, 28 oct 2026, ya no se deshacen).
"""

from datetime import date
from uuid import uuid4

from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.match_generation_block import (
    UNEXPECTED,
    MatchGenerationBlock,
)
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
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
        # Con equipos formados, la sala ya terminó
        await uow.drafts.add(
            Draft(
                id=DraftId.generate(),
                competition_id=comp_id,
                team_a_captain_id=equipo_a[0],
                team_b_captain_id=equipo_b[0],
                status=DraftStatus.COMPLETED,
            )
        )
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


def _jugador(user_id):
    return MatchPlayer.create(
        user_id=user_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )
