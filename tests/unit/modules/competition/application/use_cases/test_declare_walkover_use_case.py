"""Tests para DeclareWalkoverUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    DeclareWalkoverRequestDTO,
)
from src.modules.competition.application.use_cases.declare_walkover_use_case import (
    DeclareWalkoverUseCase,
    InvalidWalkoverError,
    MatchNotFoundError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestDeclareWalkoverUseCase:
    """Suite de tests para el caso de uso DeclareWalkoverUseCase."""

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

    async def _create_in_progress_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ) -> Competition:
        """
        Helper que crea una competicion en estado IN_PROGRESS.

        Returns:
            Competition en estado IN_PROGRESS.
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
        competition.start()

        async with uow:
            await uow.competitions.add(competition)

        return competition

    def _create_match_players(self):
        """Helper que crea jugadores para un partido."""
        player_a = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        player_b = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=[],
        )
        return player_a, player_b

    async def test_should_declare_walkover(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se puede declarar walkover correctamente.

        Given: Una competicion IN_PROGRESS con una ronda IN_PROGRESS y un partido SCHEDULED
        When: El creador declara walkover para el equipo A con razon
        Then: El partido cambia a estado WALKOVER con equipo ganador A
        """
        # Arrange
        competition = await self._create_in_progress_competition(uow, creator_id)

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()
        round_entity.start()

        player_a, player_b = self._create_match_players()
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = DeclareWalkoverUseCase(uow=uow)
        request = DeclareWalkoverRequestDTO(
            match_id=match.id.value,
            winning_team="A",
            reason="Injury",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "WALKOVER"
        assert response.winning_team == "A"
        assert response.match_id == match.id.value

    async def test_should_fail_when_match_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ):
        """
        Verifica que se lanza error cuando el partido no existe.

        Given: Un ID de partido que no existe en el repositorio
        When: Se intenta declarar walkover
        Then: Se lanza MatchNotFoundError
        """
        # Arrange
        use_case = DeclareWalkoverUseCase(uow=uow)
        request = DeclareWalkoverRequestDTO(
            match_id=uuid4(),
            winning_team="A",
            reason="No show",
        )

        # Act & Assert
        with pytest.raises(MatchNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_match_already_completed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que no se puede declarar walkover en un partido ya completado.

        Given: Una competicion IN_PROGRESS con un partido en estado COMPLETED
        When: El creador intenta declarar walkover
        Then: Se lanza InvalidWalkoverError
        """
        # Arrange
        competition = await self._create_in_progress_competition(uow, creator_id)

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()
        round_entity.start()

        player_a, player_b = self._create_match_players()
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )
        match.start()
        match.complete({"winner": "A", "score": "2&1"})

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = DeclareWalkoverUseCase(uow=uow)
        request = DeclareWalkoverRequestDTO(
            match_id=match.id.value,
            winning_team="B",
            reason="Late arrival",
        )

        # Act & Assert
        with pytest.raises(InvalidWalkoverError):
            await use_case.execute(request, creator_id)

    async def test_should_auto_complete_round_on_walkover(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que al declarar walkover en el unico partido, la ronda se auto-completa.

        Given: Una competicion IN_PROGRESS con una ronda IN_PROGRESS y un unico partido
        When: El creador declara walkover en ese partido
        Then: La ronda cambia automaticamente a COMPLETED
        """
        # Arrange
        competition = await self._create_in_progress_competition(uow, creator_id)

        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()
        round_entity.start()

        player_a, player_b = self._create_match_players()
        match = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a],
            team_b_players=[player_b],
        )

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = DeclareWalkoverUseCase(uow=uow)
        request = DeclareWalkoverRequestDTO(
            match_id=match.id.value,
            winning_team="A",
            reason="Injury",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "WALKOVER"
        assert response.round_status == "COMPLETED"
