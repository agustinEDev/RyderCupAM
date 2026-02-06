"""Tests para GenerateMatchesUseCase."""

from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    GenerateMatchesRequestDTO,
    ManualPairingDTO,
)
from src.modules.competition.application.use_cases.generate_matches_use_case import (
    GenerateMatchesUseCase,
    InsufficientPlayersError,
    NotCompetitionCreatorError,
    NoTeamAssignmentError,
    RoundNotFoundError,
    RoundNotPendingMatchesError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
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
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = pytest.mark.asyncio


class TestGenerateMatchesUseCase:
    """Suite de tests para el caso de uso GenerateMatchesUseCase."""

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
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def user_repo(self) -> AsyncMock:
        """Fixture que proporciona un mock del repositorio de usuarios."""
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

    async def _create_round_pending_matches(
        self,
        uow: InMemoryUnitOfWork,
        competition: Competition,
        golf_course_id: GolfCourseId,
        match_format: MatchFormat = MatchFormat.SINGLES,
    ) -> Round:
        """
        Helper que crea una ronda en estado PENDING_MATCHES.

        Returns:
            Round en estado PENDING_MATCHES.
        """
        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=match_format,
        )
        round_entity.mark_teams_assigned()

        async with uow:
            await uow.rounds.add(round_entity)

        return round_entity

    async def _create_teams_and_enrollments(
        self,
        uow: InMemoryUnitOfWork,
        competition: Competition,
        team_a_size: int = 2,
        team_b_size: int = 2,
    ) -> tuple[list[UserId], list[UserId]]:
        """
        Helper que crea asignacion de equipos y enrollments aprobados.

        Returns:
            Tupla con (team_a_player_ids, team_b_player_ids).
        """
        team_a = [UserId(uuid4()) for _ in range(team_a_size)]
        team_b = [UserId(uuid4()) for _ in range(team_b_size)]

        # Crear team assignment entity
        team_assignment = TeamAssignmentEntity.create(
            competition_id=competition.id,
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=team_a,
            team_b_player_ids=team_b,
        )
        async with uow:
            await uow.team_assignments.add(team_assignment)

        # Crear enrollments aprobados para todos los jugadores
        for uid in team_a + team_b:
            enrollment = Enrollment(
                id=EnrollmentId.generate(),
                competition_id=competition.id,
                user_id=uid,
                status=EnrollmentStatus.APPROVED,
            )
            async with uow:
                await uow.enrollments.add(enrollment)

        return team_a, team_b

    async def test_should_generate_singles_matches_auto(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se generan partidos SINGLES automaticamente.

        Given: Competicion CLOSED con ronda PENDING_MATCHES y equipos 2v2
        When: Se generan partidos AUTO en modo SCRATCH SINGLES
        Then: Se crean 2 partidos y la ronda pasa a SCHEDULED
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )
        await self._create_teams_and_enrollments(uow, competition, 2, 2)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.matches_generated == 2
        assert response.round_status == "SCHEDULED"
        assert response.round_id == round_entity.id.value

    async def test_should_generate_fourball_matches_auto(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se generan partidos FOURBALL automaticamente.

        Given: Competicion CLOSED con ronda FOURBALL y equipos 4v4
        When: Se generan partidos AUTO en modo SCRATCH FOURBALL
        Then: Se crean 2 partidos (2 jugadores por equipo por partido)
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.FOURBALL
        )
        await self._create_teams_and_enrollments(uow, competition, 4, 4)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.matches_generated == 2
        assert response.round_status == "SCHEDULED"

    async def test_should_generate_matches_scratch_mode(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que en modo SCRATCH todos los playing_handicap son 0.

        Given: Competicion SCRATCH con ronda SINGLES y equipos 2v2
        When: Se generan partidos automaticamente
        Then: Todos los jugadores tienen playing_handicap=0
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )
        await self._create_teams_and_enrollments(uow, competition, 2, 2)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act
        await use_case.execute(request, creator_id)

        # Assert
        matches = await uow.matches.find_by_round(round_entity.id)
        assert len(matches) == 2
        for m in matches:
            for p in m.team_a_players:
                assert p.playing_handicap == 0
            for p in m.team_b_players:
                assert p.playing_handicap == 0

    async def test_should_generate_manual_pairings(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se generan partidos con emparejamientos manuales.

        Given: Competicion CLOSED con ronda PENDING_MATCHES y equipos 2v2
        When: Se generan partidos con manual_pairings especificos
        Then: Se crea 1 partido con los jugadores indicados
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )
        team_a, team_b = await self._create_teams_and_enrollments(
            uow, competition, 2, 2
        )

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(
            round_id=round_entity.id.value,
            manual_pairings=[
                ManualPairingDTO(
                    team_a_player_ids=[team_a[0].value],
                    team_b_player_ids=[team_b[0].value],
                )
            ],
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.matches_generated == 1
        assert response.round_status == "SCHEDULED"

        matches = await uow.matches.find_by_round(round_entity.id)
        assert len(matches) == 1
        assert matches[0].team_a_players[0].user_id == team_a[0]
        assert matches[0].team_b_players[0].user_id == team_b[0]

    async def test_should_fail_when_round_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se lanza error cuando la ronda no existe.

        Given: Un ID de ronda que no existe en el repositorio
        When: Se intenta generar partidos
        Then: Se lanza RoundNotFoundError
        """
        # Arrange
        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=uuid4())

        # Act & Assert
        with pytest.raises(RoundNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que solo el creador puede generar partidos.

        Given: Una competicion CLOSED con ronda PENDING_MATCHES
        When: Un usuario que no es el creador intenta generar partidos
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id
        )

        other_user_id = UserId(uuid4())
        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_fail_when_round_not_pending_matches(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que la ronda debe estar en PENDING_MATCHES.

        Given: Una ronda en estado PENDING_TEAMS (no se llamo mark_teams_assigned)
        When: Se intenta generar partidos
        Then: Se lanza RoundNotPendingMatchesError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)

        # Crear ronda sin llamar mark_teams_assigned (queda en PENDING_TEAMS)
        round_entity = Round.create(
            competition_id=competition.id,
            golf_course_id=golf_course_id,
            round_date=date(2026, 6, 1),
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )
        async with uow:
            await uow.rounds.add(round_entity)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(RoundNotPendingMatchesError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_no_team_assignment(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se lanza error cuando no hay asignacion de equipos.

        Given: Competicion CLOSED con ronda PENDING_MATCHES pero sin team assignment
        When: Se intenta generar partidos
        Then: Se lanza NoTeamAssignmentError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id
        )
        # No se crea team assignment

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(NoTeamAssignmentError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_insufficient_players(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se lanza error cuando no hay suficientes jugadores para el formato.

        Given: Competicion con ronda FOURBALL pero equipos de solo 1 jugador
        When: Se intenta generar partidos (FOURBALL necesita 2 por equipo)
        Then: Se lanza InsufficientPlayersError
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.FOURBALL
        )
        # Solo 1 jugador por equipo (FOURBALL necesita 2)
        await self._create_teams_and_enrollments(uow, competition, 1, 1)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(InsufficientPlayersError):
            await use_case.execute(request, creator_id)

    async def test_should_regenerate_matches(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que al regenerar partidos se reemplazan los anteriores.

        Given: Ronda con partidos ya generados (estado SCHEDULED)
        When: Se vuelve a generar partidos (ronda vuelve a PENDING_MATCHES)
        Then: Los partidos antiguos se eliminan y se crean nuevos sin duplicados
        """
        # Arrange
        competition = await self._create_closed_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )
        await self._create_teams_and_enrollments(uow, competition, 2, 2)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Primera generacion
        response1 = await use_case.execute(request, creator_id)
        assert response1.matches_generated == 2

        first_matches = await uow.matches.find_by_round(round_entity.id)
        first_match_ids = {m.id for m in first_matches}
        assert len(first_match_ids) == 2

        # Volver la ronda a PENDING_MATCHES para regenerar
        # (test-only direct mutation to simulate re-generation scenario)
        round_entity._status = RoundStatus.PENDING_MATCHES
        async with uow:
            await uow.rounds.update(round_entity)

        # Segunda generacion
        response2 = await use_case.execute(request, creator_id)
        assert response2.matches_generated == 2
        assert response2.round_status == "SCHEDULED"

        # Verificar que no hay duplicados
        final_matches = await uow.matches.find_by_round(round_entity.id)
        assert len(final_matches) == 2

        # Verificar que los IDs son diferentes (nuevos partidos)
        final_match_ids = {m.id for m in final_matches}
        assert first_match_ids.isdisjoint(final_match_ids)
