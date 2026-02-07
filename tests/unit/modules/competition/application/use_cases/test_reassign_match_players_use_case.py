"""Tests para ReassignMatchPlayersUseCase."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    ReassignMatchPlayersRequestDTO,
)
from src.modules.competition.application.use_cases.reassign_match_players_use_case import (
    MatchNotScheduledError,
    PlayerNotInTeamError,
    ReassignMatchPlayersUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import (
    TeamAssignment as TeamAssignmentEntity,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.repositories.golf_course_repository import (
    IGolfCourseRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


class TestReassignMatchPlayersUseCase:
    """Suite de tests para el caso de uso ReassignMatchPlayersUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    @pytest.fixture
    def golf_course_id(self) -> GolfCourseId:
        """Fixture que proporciona un ID de campo de golf."""
        return GolfCourseId(uuid4())

    @pytest.fixture
    def gc_repo(self) -> AsyncMock:
        """Fixture que proporciona un mock del repositorio de campos de golf."""
        repo = AsyncMock(spec=IGolfCourseRepository)
        repo.find_by_id = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def user_repo(self) -> AsyncMock:
        """Fixture que proporciona un mock del repositorio de usuarios."""
        repo = AsyncMock(spec=UserRepositoryInterface)
        repo.find_by_id = AsyncMock(return_value=None)
        return repo

    async def _create_closed_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ) -> Competition:
        """
        Helper que crea una competicion en estado CLOSED.

        Returns:
            Competition en estado CLOSED.
        """
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Test Competition"),
            dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            max_players=24,
            team_assignment=TeamAssignment.MANUAL,
            team_1_name="Team A",
            team_2_name="Team B",
        )
        competition.activate()
        competition.close_enrollments()

        async with uow:
            await uow.competitions.add(competition)

        return competition

    async def _setup_teams_and_enrollments(
        self,
        uow: InMemoryUnitOfWork,
        competition: Competition,
    ):
        """
        Helper que crea 4 jugadores (2 por equipo), enrollments APPROVED y team assignment.

        Returns:
            Tuple: (player1, player2, player3, player4) where 1,2 = Team A; 3,4 = Team B.
        """
        player1 = UserId(uuid4())
        player2 = UserId(uuid4())
        player3 = UserId(uuid4())
        player4 = UserId(uuid4())

        # Crear enrollments APPROVED para los 4 jugadores
        for player_id in [player1, player2, player3, player4]:
            enrollment = Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=competition.id,
                user_id=player_id,
                tee_category=TeeCategory.AMATEUR,
            )
            async with uow:
                await uow.enrollments.add(enrollment)

        # Crear team assignment
        team_assignment = TeamAssignmentEntity.create(
            competition_id=competition.id,
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=[player1, player2],
            team_b_player_ids=[player3, player4],
        )
        async with uow:
            await uow.team_assignments.add(team_assignment)

        return player1, player2, player3, player4

    async def test_should_reassign_players_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se pueden reasignar jugadores de un partido exitosamente.

        Given: Una competicion CLOSED con equipos asignados y un partido SCHEDULED
        When: El creador reasigna nuevos jugadores del mismo equipo
        Then: Se crea un nuevo partido con los nuevos jugadores en estado SCHEDULED
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        player1, player2, player3, player4 = await self._setup_teams_and_enrollments(
            uow, competition
        )

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()

        # Match original: player1 vs player3
        original_player_a = MatchPlayer.create(
            user_id=player1,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        original_player_b = MatchPlayer.create(
            user_id=player3,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[original_player_a],
            team_b_players=[original_player_b],
        )

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = ReassignMatchPlayersUseCase(
            uow=uow,
            golf_course_repository=gc_repo,
            user_repository=user_repo,
        )

        # Reasignar: player2 (Team A) vs player4 (Team B)
        request = ReassignMatchPlayersRequestDTO(
            match_id=match.id.value,
            team_a_player_ids=[player2.value],
            team_b_player_ids=[player4.value],
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "SCHEDULED"
        # El nuevo match tiene un ID diferente al original
        assert response.match_id != match.id.value

    async def test_should_fail_when_match_not_scheduled(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que no se pueden reasignar jugadores si el partido no esta SCHEDULED.

        Given: Una competicion CLOSED con un partido en estado IN_PROGRESS
        When: El creador intenta reasignar jugadores
        Then: Se lanza MatchNotScheduledError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        player1, _player2, player3, player4 = await self._setup_teams_and_enrollments(
            uow, competition
        )

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()

        player_a = MatchPlayer.create(
            user_id=player1,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b = MatchPlayer.create(
            user_id=player3,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )
        match.start()  # IN_PROGRESS

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = ReassignMatchPlayersUseCase(
            uow=uow,
            golf_course_repository=gc_repo,
            user_repository=user_repo,
        )
        request = ReassignMatchPlayersRequestDTO(
            match_id=match.id.value,
            team_a_player_ids=[_player2.value],
            team_b_player_ids=[player4.value],
        )

        # Act & Assert
        with pytest.raises(MatchNotScheduledError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_player_not_in_team(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que no se puede asignar un jugador del equipo B en el slot del equipo A.

        Given: Una competicion CLOSED con equipos definidos y un partido SCHEDULED
        When: El creador intenta poner un jugador de Team B en la posicion de Team A
        Then: Se lanza PlayerNotInTeamError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        player1, _player2, player3, player4 = await self._setup_teams_and_enrollments(
            uow, competition
        )

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()

        player_a = MatchPlayer.create(
            user_id=player1,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b = MatchPlayer.create(
            user_id=player3,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = ReassignMatchPlayersUseCase(
            uow=uow,
            golf_course_repository=gc_repo,
            user_repository=user_repo,
        )

        # player3 pertenece al Team B, no al Team A
        request = ReassignMatchPlayersRequestDTO(
            match_id=match.id.value,
            team_a_player_ids=[player3.value],
            team_b_player_ids=[player4.value],
        )

        # Act & Assert
        with pytest.raises(PlayerNotInTeamError):
            await use_case.execute(request, creator_id)

    async def test_should_recalculate_handicaps(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que en modo SCRATCH los handicaps se recalculan a 0.

        Given: Una competicion SCRATCH CLOSED con un partido SCHEDULED
        When: El creador reasigna jugadores
        Then: El nuevo partido tiene playing_handicap=0 para ambos jugadores
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        player1, player2, player3, player4 = await self._setup_teams_and_enrollments(
            uow, competition
        )

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()

        original_player_a = MatchPlayer.create(
            user_id=player1,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        original_player_b = MatchPlayer.create(
            user_id=player3,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[original_player_a],
            team_b_players=[original_player_b],
        )

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = ReassignMatchPlayersUseCase(
            uow=uow,
            golf_course_repository=gc_repo,
            user_repository=user_repo,
        )

        request = ReassignMatchPlayersRequestDTO(
            match_id=match.id.value,
            team_a_player_ids=[player2.value],
            team_b_player_ids=[player4.value],
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert - SCRATCH mode: handicap strokes should be 0
        assert response.handicap_strokes_given == 0
        assert response.strokes_given_to_team == ""
        assert response.new_status == "SCHEDULED"
