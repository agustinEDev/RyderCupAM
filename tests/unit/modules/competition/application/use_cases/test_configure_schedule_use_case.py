"""Tests para ConfigureScheduleUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import ConfigureScheduleRequestDTO
from src.modules.competition.application.use_cases.configure_schedule_use_case import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    ConfigureScheduleUseCase,
    NoGolfCoursesError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import CompetitionGolfCourse
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestConfigureScheduleUseCase:
    """Suite de tests para el caso de uso ConfigureScheduleUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    @pytest.fixture
    def other_user_id(self) -> UserId:
        """Fixture que proporciona un ID de otro usuario (no creador)."""
        return UserId(uuid4())

    @pytest.fixture
    def golf_course_id(self) -> GolfCourseId:
        """Fixture que proporciona un ID de campo de golf."""
        return GolfCourseId(uuid4())

    async def _create_closed_competition_with_course(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ) -> Competition:
        """
        Helper que crea una competicion en estado CLOSED con un campo de golf asociado.

        Returns:
            Competition en estado CLOSED con golf course asociado.
        """
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Test"),
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

        # Add golf course via CompetitionGolfCourse
        comp_gc = CompetitionGolfCourse.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            display_order=1,
        )
        competition._golf_courses.append(comp_gc)

        async with uow:
            await uow.competitions.add(competition)

        return competition

    async def _create_closed_competition_without_courses(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ) -> Competition:
        """
        Helper que crea una competicion en estado CLOSED sin campos de golf.

        Returns:
            Competition en estado CLOSED sin golf courses.
        """
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Test No Courses"),
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

    async def test_should_configure_automatic_schedule(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se configura un schedule automatico correctamente.

        Given: Una competicion en estado CLOSED con un campo de golf asociado
        When: Se configura en modo AUTOMATIC con total_sessions=3, sessions_per_day=2
        Then: Se crean 3 rondas y se retorna response con mode=AUTOMATIC, rounds_created=3
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        use_case = ConfigureScheduleUseCase(uow=uow)
        request = ConfigureScheduleRequestDTO(
            competition_id=str(competition.id.value),
            mode="AUTOMATIC",
            total_sessions=3,
            sessions_per_day=2,
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.mode == "AUTOMATIC"
        assert response.rounds_created == 3
        assert response.competition_id == competition.id.value

        # Verify rounds were created in the repository
        async with uow:
            rounds = await uow.rounds.find_by_competition(competition.id)
        assert len(rounds) == 3

    async def test_should_return_manual_ack(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que el modo MANUAL retorna ack sin crear rondas.

        Given: Una competicion en estado CLOSED con un campo de golf asociado
        When: Se configura en modo MANUAL
        Then: Se retorna response con mode=MANUAL, rounds_created=0 y no se crean rondas
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        use_case = ConfigureScheduleUseCase(uow=uow)
        request = ConfigureScheduleRequestDTO(
            competition_id=str(competition.id.value),
            mode="MANUAL",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.mode == "MANUAL"
        assert response.rounds_created == 0

        # Verify NO rounds were created
        async with uow:
            rounds = await uow.rounds.find_by_competition(competition.id)
        assert len(rounds) == 0

    async def test_should_fail_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ):
        """
        Verifica que se lanza error cuando la competicion no existe.

        Given: Un ID de competicion que no existe
        When: Se intenta configurar el schedule
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        use_case = ConfigureScheduleUseCase(uow=uow)
        request = ConfigureScheduleRequestDTO(
            competition_id=str(uuid4()),
            mode="AUTOMATIC",
            total_sessions=3,
            sessions_per_day=2,
        )

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        other_user_id: UserId,
    ):
        """
        Verifica que solo el creador puede configurar el schedule.

        Given: Una competicion CLOSED creada por un usuario
        When: Otro usuario intenta configurar el schedule
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        use_case = ConfigureScheduleUseCase(uow=uow)
        request = ConfigureScheduleRequestDTO(
            competition_id=str(competition.id.value),
            mode="AUTOMATIC",
            total_sessions=3,
            sessions_per_day=2,
        )

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_fail_when_not_closed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que la competicion debe estar en estado CLOSED.

        Given: Una competicion en estado ACTIVE (no CLOSED)
        When: Se intenta configurar el schedule
        Then: Se lanza CompetitionNotClosedError
        """
        # Arrange - crear competicion en estado ACTIVE (no CLOSED)
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Active Competition"),
            dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            max_players=24,
            team_assignment=TeamAssignment.MANUAL,
            team_1_name="Team A",
            team_2_name="Team B",
        )
        competition.activate()

        # Asociar campo de golf
        comp_gc = CompetitionGolfCourse.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            display_order=1,
        )
        competition._golf_courses.append(comp_gc)

        async with uow:
            await uow.competitions.add(competition)

        use_case = ConfigureScheduleUseCase(uow=uow)
        request = ConfigureScheduleRequestDTO(
            competition_id=str(competition.id.value),
            mode="AUTOMATIC",
            total_sessions=3,
            sessions_per_day=2,
        )

        # Act & Assert
        with pytest.raises(CompetitionNotClosedError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_no_golf_courses(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ):
        """
        Verifica que se lanza error cuando la competicion no tiene campos de golf.

        Given: Una competicion en estado CLOSED sin campos de golf asociados
        When: Se intenta configurar el schedule en modo AUTOMATIC
        Then: Se lanza NoGolfCoursesError
        """
        # Arrange - competicion CLOSED sin golf courses
        competition = await self._create_closed_competition_without_courses(
            uow, creator_id
        )
        use_case = ConfigureScheduleUseCase(uow=uow)
        request = ConfigureScheduleRequestDTO(
            competition_id=str(competition.id.value),
            mode="AUTOMATIC",
            total_sessions=3,
            sessions_per_day=2,
        )

        # Act & Assert
        with pytest.raises(NoGolfCoursesError):
            await use_case.execute(request, creator_id)
