"""
Quién descansa en cada sesión (#710, 24 sep).

Con equipos desiguales —el draft admite uno de diferencia— el que sobra se
quedaba sin partido y nadie lo decía: en un 2 contra 3 salían 2 partidos y el
tercero no aparecía en ningún sitio. La agenda dice ahora quién descansa.

    #   caso                                             | resting_player_ids
    ----|------------------------------------------------|-------------------
    Q1  draft 2 contra 3, individuales, 2 partidos      | el tercero de B
    Q2  sesión sin partidos todavía                     | nadie: no se sabe
    Q3  uno del equipo que se retiró                    | no sale: no está
    Q4  juegan todos                                    | nadie
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import GetScheduleRequestDTO
from src.modules.competition.application.use_cases.get_schedule_use_case import (
    GetScheduleUseCase,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import (
    TeamAssignment as Reparto,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_status import EnrollmentStatus
from src.modules.competition.domain.value_objects.match_format import MatchFormat
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
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
)

pytestmark = pytest.mark.asyncio


def _jugador(uid: UserId) -> MatchPlayer:
    return MatchPlayer.create(
        user_id=uid,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )


async def _dos_contra_tres(partidos: bool = True, en_b: int = 3):
    """Un draft de 2 contra 3 (o los que se digan en B) y una sesión de individuales."""
    uow = InMemoryUnitOfWork()
    creada = await create_competition(uow, UserId(uuid4()))
    comp_id = CompetitionId(creada.id)
    a = [UserId(uuid4()) for _ in range(2)]
    b = [UserId(uuid4()) for _ in range(en_b)]
    for uid in [*a, *b]:
        await create_approved_enrollment(uow, creada.id, uid)
    ronda = Round.create(
        competition_id=comp_id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=date(2026, 6, 1),
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    async with uow:
        await uow.team_assignments.add(
            Reparto.create(
                competition_id=comp_id,
                mode=TeamAssignmentMode.DRAFT,
                team_a_player_ids=a,
                team_b_player_ids=b,
            )
        )
        await uow.rounds.add(ronda)
        if partidos:
            for n, (ja, jb) in enumerate(zip(a, b[:2], strict=True), start=1):
                await uow.matches.add(
                    Match.create(
                        round_id=ronda.id,
                        match_number=n,
                        team_a_players=[_jugador(ja)],
                        team_b_players=[_jugador(jb)],
                    )
                )
    return uow, comp_id, a, b


async def _descansan(uow, comp_id) -> list:
    agenda = await GetScheduleUseCase(uow=uow).execute(
        GetScheduleRequestDTO(competition_id=str(comp_id.value))
    )
    return agenda.days[0].rounds[0].resting_player_ids


async def test_q1_el_que_sobra_descansa_y_se_dice():
    uow, comp_id, _, b = await _dos_contra_tres()

    assert await _descansan(uow, comp_id) == [b[2].value]


async def test_q2_sin_partidos_todavia_no_se_sabe_quien_descansa():
    uow, comp_id, _, _ = await _dos_contra_tres(partidos=False)

    assert await _descansan(uow, comp_id) == []


async def test_q3_un_retirado_no_descansa_no_esta():
    uow, comp_id, _, b = await _dos_contra_tres()
    async with uow:
        inscripcion = await uow.enrollments.find_by_user_and_competition(b[2], comp_id)
        inscripcion._status = EnrollmentStatus.WITHDRAWN
        await uow.enrollments.update(inscripcion)

    assert await _descansan(uow, comp_id) == []


async def test_q4_si_juegan_todos_no_descansa_nadie():
    uow, comp_id, _, _ = await _dos_contra_tres(en_b=2)

    assert await _descansan(uow, comp_id) == []
