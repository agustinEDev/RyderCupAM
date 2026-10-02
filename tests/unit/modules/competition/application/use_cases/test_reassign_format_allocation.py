"""
Reasignar reparte los golpes como generar, formato a formato (BE #477).

Reasignar daba a cada jugador TODO su hándicap de juego como golpes, fuera cual
fuera el formato, y `match_opener` copia esos golpes a la anotación: tras
cualquier reasignación el resultado del partido salía mal. Los tests de
reasignar solo cubrían SCRATCH.

Todos los casos usan una barra neutra (slope 113, Course Rating igual al par),
así que el Course Handicap coincide con el Handicap Index y las cuentas se
pueden hacer a mano.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    ReassignMatchPlayersRequestDTO,
)
from src.modules.competition.application.services.match_players_builder import (
    TeeColorNotFoundError,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    PlayerNotEnrolledError,
    ReassignMatchPlayersUseCase,
    WrongNumberOfPlayersError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import (
    TeamAssignment as TeamAssignmentEntity,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio


async def _reassign(
    match_format: MatchFormat,
    team_a_handicaps: list[str],
    team_b_handicaps: list[str],
    tee_color: TeeColor = TeeColor.YELLOW,
    enrolled: bool = True,
    sent_a: int | None = None,
    sent_b: int | None = None,
):
    """
    Monta una competición con hándicap, un partido ya generado con otros
    jugadores, y reasigna a los jugadores con estos hándicaps.

    Returns:
        (jugadores del equipo A, jugadores del equipo B) del partido nuevo, en
        el orden de los hándicaps recibidos
    """
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    per_side = max(len(team_a_handicaps), len(team_b_handicaps))

    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName("Reassign Cup"),
        dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        max_players=24,
        team_assignment=TeamAssignment.MANUAL,
        team_1_name="Norte",
        team_2_name="Sur",
    )
    competition.activate()
    competition.close_enrollments()
    async with uow:
        await uow.competitions.add(competition)

    # Los que estaban en el partido (con cualquier hándicap) y los que entran
    old_a = [UserId(uuid4()) for _ in range(per_side)]
    old_b = [UserId(uuid4()) for _ in range(per_side)]
    new_a = [UserId(uuid4()) for _ in team_a_handicaps]
    new_b = [UserId(uuid4()) for _ in team_b_handicaps]
    handicaps = dict(
        zip(
            [*old_a, *old_b, *new_a, *new_b],
            ["0"] * (2 * per_side) + team_a_handicaps + team_b_handicaps,
            strict=True,
        )
    )
    for player_id, handicap in handicaps.items():
        if not enrolled and player_id in new_b:
            continue
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=competition.id,
            user_id=player_id,
            custom_handicap=Decimal(handicap),
            tee_color=tee_color,
        )
        async with uow:
            await uow.enrollments.add(enrollment)

    async with uow:
        await uow.team_assignments.add(
            TeamAssignmentEntity.create(
                competition_id=competition.id,
                mode=TeamAssignmentMode.MANUAL,
                team_a_player_ids=[*old_a, *new_a],
                team_b_player_ids=[*old_b, *new_b],
            )
        )

    golf_course = GolfCourse.create(
        name="Neutral",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=None,
                identifier="Yellow",
                course_rating=72.0,
                slope_rating=113,
            )
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    gc_repo = AsyncMock(spec=IGolfCourseRepository)
    gc_repo.find_by_id = AsyncMock(return_value=golf_course)
    user_repo = AsyncMock(spec=UserRepositoryInterface)
    user_repo.find_by_id = AsyncMock(return_value=None)

    round_entity = Round.create(
        competition_id=competition.id,
        golf_course_id=GolfCourseId(uuid4()),
        round_date=date(2026, 6, 1),
        session_type=SessionType.MORNING,
        match_format=match_format,
    )
    round_entity.mark_teams_assigned()
    round_entity.mark_matches_generated()

    def _placeholder(user_id):
        return MatchPlayer.create(
            user_id=user_id, playing_handicap=0, tee_color=TeeColor.YELLOW, strokes_received=[]
        )

    match = Match.create(
        round_id=round_entity.id,
        match_number=1,
        team_a_players=[_placeholder(u) for u in old_a],
        team_b_players=[_placeholder(u) for u in old_b],
    )
    async with uow:
        await uow.rounds.add(round_entity)
        await uow.matches.add(match)

    use_case = ReassignMatchPlayersUseCase(
        uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
    )
    response = await use_case.execute(
        ReassignMatchPlayersRequestDTO(
            match_id=match.id.value,
            team_a_player_ids=[u.value for u in new_a[: sent_a if sent_a is not None else None]],
            team_b_player_ids=[u.value for u in new_b[: sent_b if sent_b is not None else None]],
        ),
        creator_id,
    )

    async with uow:
        new_match = await uow.matches.find_by_id(MatchId(response.match_id))
    by_id_a = {p.user_id: p for p in new_match.team_a_players}
    by_id_b = {p.user_id: p for p in new_match.team_b_players}
    return [by_id_a[u] for u in new_a], [by_id_b[u] for u in new_b]


class TestSingles:
    async def test_only_the_higher_handicap_receives_the_difference(self):
        """10 contra 18 al 100 %: el de 18 recibe 8, en los hoyos de SI 1 a 8."""
        (a,), (b,) = await _reassign(MatchFormat.SINGLES, ["10"], ["18"])

        assert list(a.strokes_received) == []
        assert list(b.strokes_received) == [1, 2, 3, 4, 5, 6, 7, 8]
        # Se guarda el hándicap de juego de cada uno, no la diferencia
        assert a.playing_handicap == 10
        assert b.playing_handicap == 18

    async def test_equal_handicaps_receive_nothing(self):
        (a,), (b,) = await _reassign(MatchFormat.SINGLES, ["12"], ["12"])

        assert list(a.strokes_received) == []
        assert list(b.strokes_received) == []


class TestFourball:
    async def test_each_player_receives_the_difference_to_the_lowest(self):
        """
        Al 90 % sobre la diferencia con el más bajo (6):
        10 -> 3.6 -> 4, 14 -> 7.2 -> 7, 18 -> 10.8 -> 11, 6 -> 0.
        """
        (a1, a2), (b1, b2) = await _reassign(MatchFormat.FOURBALL, ["10", "14"], ["18", "6"])

        assert [len(p.strokes_received) for p in (a1, a2, b1, b2)] == [4, 7, 11, 0]


class TestFoursomes:
    async def test_the_team_receives_the_allowance_on_the_difference_of_averages(self):
        """
        Medias 12 (10 y 14) y 14 (20 y 8): diferencia 2, al 50 % es 1. Lo
        recibe el equipo B entero, los dos jugadores el mismo hoyo.
        """
        (a1, a2), (b1, b2) = await _reassign(MatchFormat.FOURSOMES, ["10", "14"], ["20", "8"])

        assert list(a1.strokes_received) == list(a2.strokes_received) == []
        assert list(b1.strokes_received) == list(b2.strokes_received) == [1]


class TestLikeGenerating:
    async def test_the_handicap_index_snapshot_is_kept(self):
        """Generar guarda el index de cada jugador; reasignar no lo guardaba."""
        (a,), (b,) = await _reassign(MatchFormat.SINGLES, ["10.4"], ["18.2"])

        assert a.player_handicap == Decimal("10.4")
        assert b.player_handicap == Decimal("18.2")

    async def test_a_tee_without_rating_is_a_tee_not_found_error(self):
        """
        Era un ValueError, que la API convertía en un 500. Ahora es el mismo
        error que al generar, que la API da como 400 con su mensaje.
        """
        with pytest.raises(TeeColorNotFoundError):
            await _reassign(MatchFormat.SINGLES, ["10"], ["18"], tee_color=TeeColor.RED)

    async def test_a_player_without_an_approved_enrollment_is_rejected(self):
        """
        Lo comprobaba el reparto viejo de reasignar, sin test. Se conserva:
        sin inscripción no se sabe desde qué barra juega ni con qué hándicap.
        """
        with pytest.raises(PlayerNotEnrolledError):
            await _reassign(MatchFormat.SINGLES, ["10"], ["18"], enrolled=False)


class TestPlayersPerSide:
    """
    Cada lado trae exactamente los jugadores de su formato (revisión local de
    la #477). El reparto individual lee el primero de cada lado: sin esto, un
    2 contra 2 en individual se guardaba en silencio como 1 contra 1.
    """

    async def test_two_per_side_in_singles(self):
        with pytest.raises(WrongNumberOfPlayersError):
            await _reassign(MatchFormat.SINGLES, ["10", "12"], ["18", "20"])

    async def test_uneven_sides(self):
        with pytest.raises(WrongNumberOfPlayersError):
            await _reassign(MatchFormat.FOURBALL, ["10", "12"], ["18", "20"], sent_b=1)

    async def test_an_empty_side(self):
        with pytest.raises(WrongNumberOfPlayersError):
            await _reassign(MatchFormat.SINGLES, ["10"], ["18"], sent_a=0)

    async def test_one_per_side_in_fourball(self):
        with pytest.raises(WrongNumberOfPlayersError):
            await _reassign(MatchFormat.FOURBALL, ["10"], ["18"])
