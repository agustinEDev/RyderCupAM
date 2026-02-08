"""Tests para UpdateMatchStatusUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    UpdateMatchStatusRequestDTO,
)
from src.modules.competition.application.use_cases.update_match_status_use_case import (
    InvalidActionError,
    UpdateMatchStatusUseCase,
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
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


class TestUpdateMatchStatusUseCase:
    """Suite de tests para el caso de uso UpdateMatchStatusUseCase."""

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
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        return player_a, player_b

    async def test_should_start_match(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se puede iniciar un partido con accion START.

        Given: Una competicion IN_PROGRESS con una ronda SCHEDULED y un partido
        When: El creador ejecuta accion START sobre el partido
        Then: El partido cambia a estado IN_PROGRESS
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

        use_case = UpdateMatchStatusUseCase(uow=uow)
        request = UpdateMatchStatusRequestDTO(
            match_id=match.id.value,
            action="START",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "IN_PROGRESS"
        assert response.match_id == match.id.value

    async def test_should_complete_match(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se puede completar un partido con accion COMPLETE.

        Given: Una competicion IN_PROGRESS con una ronda IN_PROGRESS y un partido iniciado
        When: El creador ejecuta accion COMPLETE con resultado
        Then: El partido cambia a estado COMPLETED
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

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = UpdateMatchStatusUseCase(uow=uow)
        request = UpdateMatchStatusRequestDTO(
            match_id=match.id.value,
            action="COMPLETE",
            result={"winner": "A", "score": "3&2"},
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "COMPLETED"
        assert response.match_id == match.id.value

    async def test_should_auto_start_round(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que al iniciar un partido, la ronda se auto-inicia si esta SCHEDULED.

        Given: Una competicion IN_PROGRESS con una ronda en estado SCHEDULED
        When: El creador inicia un partido de esa ronda
        Then: La ronda cambia automaticamente a IN_PROGRESS
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
        # Round stays in SCHEDULED state

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

        use_case = UpdateMatchStatusUseCase(uow=uow)
        request = UpdateMatchStatusRequestDTO(
            match_id=match.id.value,
            action="START",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "IN_PROGRESS"
        assert response.round_status == "IN_PROGRESS"

    async def test_should_auto_complete_round(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que al completar el ultimo partido, la ronda se auto-completa.

        Given: Una competicion IN_PROGRESS con una ronda IN_PROGRESS y un unico partido iniciado
        When: El creador completa ese unico partido
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
        match.start()

        async with uow:
            await uow.rounds.add(round_entity)
            await uow.matches.add(match)

        use_case = UpdateMatchStatusUseCase(uow=uow)
        request = UpdateMatchStatusRequestDTO(
            match_id=match.id.value,
            action="COMPLETE",
            result={"winner": "A", "score": "3&2"},
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.new_status == "COMPLETED"
        assert response.round_status == "COMPLETED"

    async def test_should_fail_when_invalid_action(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que una accion invalida lanza InvalidActionError.

        Given: Una competicion IN_PROGRESS con una ronda y un partido
        When: El creador ejecuta una accion no reconocida ("INVALID")
        Then: Se lanza InvalidActionError
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

        use_case = UpdateMatchStatusUseCase(uow=uow)
        request = UpdateMatchStatusRequestDTO(
            match_id=match.id.value,
            action="INVALID",
        )

        # Act & Assert
        with pytest.raises(InvalidActionError):
            await use_case.execute(request, creator_id)
