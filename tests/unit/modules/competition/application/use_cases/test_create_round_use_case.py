"""Tests para CreateRoundUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    CreateRoundRequestDTO,
)
from src.modules.competition.application.use_cases.create_round_use_case import (
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    CreateRoundUseCase,
    DateOutOfRangeError,
    DuplicateSessionError,
    GolfCourseNotInCompetitionError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestCreateRoundUseCase:
    """Suite de tests para el caso de uso CreateRoundUseCase."""

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

    async def test_should_create_round_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se crea una ronda correctamente con datos validos.

        Given: Una competicion en estado CLOSED con un campo de golf asociado
        When: El creador crea una ronda con SINGLES, MORNING y fecha valida
        Then: La ronda se crea en estado PENDING_TEAMS y se persiste
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=competition.id.value,
            golf_course_id=golf_course_id.value,
            round_date=date(2026, 6, 1),
            session_type="MORNING",
            match_format="SINGLES",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.id is not None
        assert response.competition_id == competition.id.value
        assert response.status == "PENDING_TEAMS"
        assert response.created_at is not None

    async def test_should_fail_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se lanza error cuando la competicion no existe.

        Given: Un ID de competicion que no existe
        When: Se intenta crear una ronda
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=uuid4(),
            golf_course_id=golf_course_id.value,
            round_date=date(2026, 6, 1),
            session_type="MORNING",
            match_format="SINGLES",
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
        Verifica que solo el creador puede crear rondas.

        Given: Una competicion CLOSED creada por un usuario
        When: Otro usuario intenta crear una ronda
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=competition.id.value,
            golf_course_id=golf_course_id.value,
            round_date=date(2026, 6, 1),
            session_type="MORNING",
            match_format="SINGLES",
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
        When: Se intenta crear una ronda
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

        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=competition.id.value,
            golf_course_id=golf_course_id.value,
            round_date=date(2026, 6, 1),
            session_type="MORNING",
            match_format="SINGLES",
        )

        # Act & Assert
        with pytest.raises(CompetitionNotClosedError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_golf_course_not_in_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que el campo de golf debe estar asociado a la competicion.

        Given: Una competicion CLOSED con un campo de golf asociado
        When: Se intenta crear una ronda con un campo de golf diferente
        Then: Se lanza GolfCourseNotInCompetitionError
        """
        # Arrange
        await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        competition = (await uow.competitions.find_all())[0]
        other_golf_course_id = GolfCourseId(uuid4())

        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=competition.id.value,
            golf_course_id=other_golf_course_id.value,
            round_date=date(2026, 6, 1),
            session_type="MORNING",
            match_format="SINGLES",
        )

        # Act & Assert
        with pytest.raises(GolfCourseNotInCompetitionError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_duplicate_session(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que no se puede crear una sesion duplicada en la misma fecha.

        Given: Una ronda MORNING ya existente para una fecha
        When: Se intenta crear otra ronda MORNING en la misma fecha
        Then: Se lanza DuplicateSessionError
        """
        # Arrange - crear competicion y primera ronda
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )

        # Crear primera ronda
        first_round = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with uow:
            await uow.rounds.add(first_round)

        # Intentar crear segunda ronda con misma fecha y session_type
        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=competition.id.value,
            golf_course_id=golf_course_id.value,
            round_date=date(2026, 6, 1),
            session_type="MORNING",
            match_format="FOURBALL",
        )

        # Act & Assert
        with pytest.raises(DuplicateSessionError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_date_out_of_range(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que la fecha de la ronda debe estar dentro del rango de la competicion.

        Given: Una competicion con fechas del 1 al 3 de junio de 2026
        When: Se intenta crear una ronda con fecha 10 de junio de 2026
        Then: Se lanza DateOutOfRangeError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        use_case = CreateRoundUseCase(uow=uow)
        request = CreateRoundRequestDTO(
            competition_id=competition.id.value,
            golf_course_id=golf_course_id.value,
            round_date=date(2026, 6, 10),  # Fuera del rango 1-3 junio
            session_type="MORNING",
            match_format="SINGLES",
        )

        # Act & Assert
        with pytest.raises(DateOutOfRangeError):
            await use_case.execute(request, creator_id)
