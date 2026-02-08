"""Tests para DeleteRoundUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    DeleteRoundRequestDTO,
)
from src.modules.competition.application.use_cases.delete_round_use_case import (
    DeleteRoundUseCase,
    NotCompetitionCreatorError,
    RoundNotFoundError,
    RoundNotModifiableError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
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


class TestDeleteRoundUseCase:
    """Suite de tests para el caso de uso DeleteRoundUseCase."""

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
    def other_user_id(self) -> UserId:
        """Fixture que proporciona un ID de otro usuario (no creador)."""
        return UserId(uuid4())

    async def _create_closed_competition_with_course(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        start_date: date = date(2026, 6, 1),
        end_date: date = date(2026, 6, 3),
    ) -> Competition:
        """
        Helper que crea una competicion en estado CLOSED con un campo de golf asociado.

        Returns:
            Competition en estado CLOSED con golf course asociado.
        """
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Test Competition"),
            dates=DateRange(start_date=start_date, end_date=end_date),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            max_players=24,
            team_assignment=TeamAssignment.MANUAL,
            team_1_name="Team A",
            team_2_name="Team B",
        )
        competition.activate()
        competition.close_enrollments()

        # Asociar campo de golf a la competicion
        comp_gc = CompetitionGolfCourse.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            display_order=1,
        )
        competition._golf_courses.append(comp_gc)

        async with uow:
            await uow.competitions.add(competition)

        return competition

    async def _create_round_for_competition(
        self,
        uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course_id: GolfCourseId,
        round_date: date = date(2026, 6, 1),
        session_type: SessionType = SessionType.MORNING,
        match_format: MatchFormat = MatchFormat.SINGLES,
    ) -> Round:
        """
        Helper que crea una ronda asociada a una competicion.

        Returns:
            Round en estado PENDING_TEAMS.
        """
        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=round_date,
            session_type=session_type,
            match_format=match_format,
        )
        async with uow:
            await uow.rounds.add(round_entity)

        return round_entity

    async def test_should_delete_round_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se elimina una ronda correctamente.

        Given: Una ronda en estado PENDING_TEAMS
        When: El creador la elimina
        Then: La ronda se elimina y response.deleted es True
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        use_case = DeleteRoundUseCase(uow=uow)
        request = DeleteRoundRequestDTO(round_id=round_entity.id.value)

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.deleted is True
        assert response.id == round_entity.id.value
        assert response.matches_deleted == 0
        assert response.deleted_at is not None

    async def test_should_cascade_delete_matches(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que al eliminar una ronda se eliminan sus partidos en cascada.

        Given: Una ronda con 2 partidos asociados
        When: El creador elimina la ronda
        Then: Se eliminan la ronda y los 2 partidos (matches_deleted == 2)
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        # Crear 2 partidos asociados a la ronda
        player_a1 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b1 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match_1 = Match.create(
            round_id=round_entity.id,
            match_number=1,
            team_a_players=[player_a1],
            team_b_players=[player_b1],
        )

        player_a2 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        player_b2 = MatchPlayer.create(
            user_id=UserId(uuid4()),
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            strokes_received=[],
            tee_gender=Gender.MALE,
        )
        match_2 = Match.create(
            round_id=round_entity.id,
            match_number=2,
            team_a_players=[player_a2],
            team_b_players=[player_b2],
        )

        async with uow:
            await uow.matches.add(match_1)
            await uow.matches.add(match_2)

        use_case = DeleteRoundUseCase(uow=uow)
        request = DeleteRoundRequestDTO(round_id=round_entity.id.value)

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.deleted is True
        assert response.matches_deleted == 2

    async def test_should_fail_when_round_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ):
        """
        Verifica que se lanza error cuando la ronda no existe.

        Given: Un ID de ronda que no existe
        When: Se intenta eliminar la ronda
        Then: Se lanza RoundNotFoundError
        """
        # Arrange
        use_case = DeleteRoundUseCase(uow=uow)
        request = DeleteRoundRequestDTO(round_id=uuid4())

        # Act & Assert
        with pytest.raises(RoundNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        other_user_id: UserId,
    ):
        """
        Verifica que solo el creador puede eliminar rondas.

        Given: Una ronda creada por un usuario
        When: Otro usuario intenta eliminar la ronda
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        use_case = DeleteRoundUseCase(uow=uow)
        request = DeleteRoundRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_fail_when_not_modifiable(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que no se puede eliminar una ronda en estado SCHEDULED.

        Given: Una ronda en estado SCHEDULED (tras mark_teams_assigned y mark_matches_generated)
        When: Se intenta eliminar la ronda
        Then: Se lanza RoundNotModifiableError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        # Transicionar a SCHEDULED
        round_entity.mark_teams_assigned()
        round_entity.mark_matches_generated()

        async with uow:
            await uow.rounds.update(round_entity)

        use_case = DeleteRoundUseCase(uow=uow)
        request = DeleteRoundRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(RoundNotModifiableError):
            await use_case.execute(request, creator_id)
