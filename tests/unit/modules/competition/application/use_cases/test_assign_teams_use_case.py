"""Tests para AssignTeamsUseCase."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import AssignTeamsRequestDTO
from src.modules.competition.application.use_cases.assign_teams_use_case import (
    AssignTeamsUseCase,
    CompetitionNotClosedError,
    CompetitionNotFoundError,
    InsufficientPlayersError,
    NotCompetitionCreatorError,
    OddPlayersError,
    PlayerNotEnrolledError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestAssignTeamsUseCase:
    """Suite de tests para el caso de uso AssignTeamsUseCase."""

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
    def user_repo(self) -> AsyncMock:
        """Fixture que proporciona un mock de UserRepositoryInterface."""
        repo = AsyncMock()
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

    async def _add_approved_enrollment(
        self,
        uow: InMemoryUnitOfWork,
        competition: Competition,
        user_id: UserId | None = None,
        custom_handicap: Decimal | None = None,
    ) -> Enrollment:
        """
        Helper que crea un enrollment aprobado individual.

        Args:
            uow: Unit of Work en memoria.
            competition: Competicion a la que se inscribe.
            user_id: ID del jugador (genera uno si es None).
            custom_handicap: Handicap personalizado (opcional).

        Returns:
            Enrollment aprobado.
        """
        uid = user_id or UserId(uuid4())
        enrollment = Enrollment.direct_enroll(
            id=EnrollmentId.generate(),
            competition_id=competition.id,
            user_id=uid,
            custom_handicap=custom_handicap,
        )
        async with uow:
            await uow.enrollments.add(enrollment)
        return enrollment

    async def test_should_assign_teams_automatically(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se asignan equipos automaticamente con SnakeDraft.

        Given: Una competicion CLOSED con 4 jugadores aprobados con handicap
        When: Se solicita asignacion AUTOMATIC
        Then: Se crean dos equipos de 2 jugadores cada uno, modo AUTOMATIC
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        # Crear 4 enrollments aprobados con custom_handicap
        for i in range(4):
            await self._add_approved_enrollment(
                uow,
                competition,
                custom_handicap=Decimal(str(10 + i * 5)),
            )

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="AUTOMATIC",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert len(response.team_a_player_ids) == 2
        assert len(response.team_b_player_ids) == 2
        assert response.mode == "AUTOMATIC"
        assert response.competition_id == competition.id.value

    async def test_should_assign_teams_manually(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se asignan equipos manualmente con listas explicitas.

        Given: Una competicion CLOSED con 4 jugadores aprobados
        When: Se solicita asignacion MANUAL con listas de jugadores
        Then: Los equipos contienen exactamente los jugadores indicados
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        e1 = await self._add_approved_enrollment(uow, competition)
        e2 = await self._add_approved_enrollment(uow, competition)
        e3 = await self._add_approved_enrollment(uow, competition)
        e4 = await self._add_approved_enrollment(uow, competition)

        player1_id = e1.user_id.value
        player2_id = e2.user_id.value
        player3_id = e3.user_id.value
        player4_id = e4.user_id.value

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="MANUAL",
            team_a_player_ids=[player1_id, player2_id],
            team_b_player_ids=[player3_id, player4_id],
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.mode == "MANUAL"
        assert set(response.team_a_player_ids) == {player1_id, player2_id}
        assert set(response.team_b_player_ids) == {player3_id, player4_id}

    async def test_should_fail_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se lanza error cuando la competicion no existe.

        Given: Un ID de competicion que no existe en el repositorio
        When: Se intenta asignar equipos
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=uuid4(),
            mode="AUTOMATIC",
        )

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        other_user_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que solo el creador puede asignar equipos.

        Given: Una competicion CLOSED creada por un usuario
        When: Otro usuario intenta asignar equipos
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="AUTOMATIC",
        )

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_fail_when_not_closed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que la competicion debe estar en estado CLOSED.

        Given: Una competicion en estado ACTIVE (no CLOSED)
        When: Se intenta asignar equipos
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

        async with uow:
            await uow.competitions.add(competition)

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="AUTOMATIC",
        )

        # Act & Assert
        with pytest.raises(CompetitionNotClosedError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_insufficient_players(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se necesitan al menos 2 jugadores aprobados.

        Given: Una competicion CLOSED con solo 1 jugador aprobado
        When: Se intenta asignar equipos
        Then: Se lanza InsufficientPlayersError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        # Solo 1 enrollment aprobado
        await self._add_approved_enrollment(uow, competition)

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="AUTOMATIC",
        )

        # Act & Assert
        with pytest.raises(InsufficientPlayersError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_odd_players(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se necesita un numero par de jugadores.

        Given: Una competicion CLOSED con 3 jugadores aprobados
        When: Se intenta asignar equipos
        Then: Se lanza OddPlayersError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        # 3 enrollments aprobados (numero impar)
        for _ in range(3):
            await self._add_approved_enrollment(uow, competition)

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="AUTOMATIC",
        )

        # Act & Assert
        with pytest.raises(OddPlayersError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_manual_player_not_enrolled(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        user_repo: AsyncMock,
    ):
        """
        Verifica que en modo MANUAL todos los jugadores deben estar inscritos.

        Given: Una competicion CLOSED con 4 jugadores aprobados
        When: Se asignan equipos MANUAL con un UUID que no es un enrollee
        Then: Se lanza PlayerNotEnrolledError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        e1 = await self._add_approved_enrollment(uow, competition)
        e2 = await self._add_approved_enrollment(uow, competition)
        e3 = await self._add_approved_enrollment(uow, competition)
        await self._add_approved_enrollment(uow, competition)

        # Un UUID que no es de ningun enrollee
        unknown_player_id = uuid4()

        use_case = AssignTeamsUseCase(uow=uow, user_repository=user_repo)
        request = AssignTeamsRequestDTO(
            competition_id=competition.id.value,
            mode="MANUAL",
            team_a_player_ids=[e1.user_id.value, e2.user_id.value],
            team_b_player_ids=[e3.user_id.value, unknown_player_id],
        )

        # Act & Assert
        with pytest.raises(PlayerNotEnrolledError):
            await use_case.execute(request, creator_id)
