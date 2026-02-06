"""Tests para GenerateMatchesUseCase."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
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
    TeeCategoryNotFoundError,
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
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.handicap import Handicap
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

    # =========================================================================
    # HANDICAP MODE TESTS
    # =========================================================================

    async def _create_handicap_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ) -> Competition:
        """
        Helper que crea una competicion HANDICAP en estado CLOSED.

        Returns:
            Competition en estado CLOSED con play_mode=HANDICAP.
        """
        competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName("Handicap Competition"),
            dates=DateRange(start_date=date(2026, 6, 1), end_date=date(2026, 6, 3)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.HANDICAP,
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

    def _build_mock_golf_course(
        self,
        tee_categories: list[TeeCategory] | None = None,
    ) -> MagicMock:
        """
        Helper que construye un mock de GolfCourse con tees y 18 holes.

        Args:
            tee_categories: Categorias de tee a incluir.
                Defaults to [AMATEUR_MALE].

        Returns:
            Mock de GolfCourse con tees y holes configurados.
        """
        if tee_categories is None:
            tee_categories = [TeeCategory.AMATEUR_MALE]

        # Crear tees mock
        tees = []
        for cat in tee_categories:
            tee = MagicMock()
            tee.category = cat
            tee.course_rating = Decimal("71.2")
            tee.slope_rating = 128
            tees.append(tee)

        # Crear 18 holes mock con pars y stroke indices
        holes = []
        pars = [4, 3, 5, 4, 4, 3, 4, 5, 4, 4, 3, 5, 4, 4, 3, 4, 5, 4]
        for i in range(1, 19):
            hole = MagicMock()
            hole.number = i
            hole.par = pars[i - 1]
            hole.stroke_index = i  # stroke_index 1-18 in order
            holes.append(hole)

        golf_course = MagicMock()
        golf_course.tees = tees
        golf_course.holes = holes

        return golf_course

    def _build_mock_user(self, user_id: UserId, handicap_value: float) -> MagicMock:
        """
        Helper que construye un mock de User con un handicap.

        Args:
            user_id: ID del usuario.
            handicap_value: Valor del handicap.

        Returns:
            Mock de User con handicap configurado.
        """
        user = MagicMock()
        user.id = user_id
        user.handicap = Handicap(handicap_value)
        return user

    async def _create_teams_and_enrollments_with_tees(
        self,
        uow: InMemoryUnitOfWork,
        competition: Competition,
        team_a_size: int = 2,
        team_b_size: int = 2,
        tee_category: TeeCategory = TeeCategory.AMATEUR_MALE,
    ) -> tuple[list[UserId], list[UserId]]:
        """
        Helper que crea equipos y enrollments con tee_category asignado.

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

        # Crear enrollments aprobados con tee_category
        for uid in team_a + team_b:
            enrollment = Enrollment(
                id=EnrollmentId.generate(),
                competition_id=competition.id,
                user_id=uid,
                status=EnrollmentStatus.APPROVED,
                tee_category=tee_category,
            )
            async with uow:
                await uow.enrollments.add(enrollment)

        return team_a, team_b

    async def test_should_generate_matches_handicap_mode(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que en modo HANDICAP se calculan playing_handicap y strokes_received.

        Given: Competicion HANDICAP con campo de golf (AMATEUR_MALE tee) y jugadores con handicap
        When: Se generan partidos automaticamente
        Then: Todos los jugadores tienen playing_handicap > 0 y strokes_received no vacio
        """
        # Arrange
        competition = await self._create_handicap_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )
        await self._create_teams_and_enrollments_with_tees(
            uow, competition, 2, 2, TeeCategory.AMATEUR_MALE
        )

        # Mock golf course con tee AMATEUR_MALE
        mock_gc = self._build_mock_golf_course([TeeCategory.AMATEUR_MALE])
        gc_repo.find_by_id = AsyncMock(return_value=mock_gc)

        # Mock user_repo para devolver usuarios con handicap
        async def mock_find_user(uid):
            return self._build_mock_user(uid, 15.0)

        user_repo.find_by_id = AsyncMock(side_effect=mock_find_user)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.matches_generated == 2
        assert response.round_status == "SCHEDULED"

        matches = await uow.matches.find_by_round(round_entity.id)
        assert len(matches) == 2
        for m in matches:
            for p in m.team_a_players:
                assert p.playing_handicap > 0, "HANDICAP mode should produce non-zero playing_handicap"
                assert len(p.strokes_received) > 0, "HANDICAP mode should produce strokes_received"
            for p in m.team_b_players:
                assert p.playing_handicap > 0, "HANDICAP mode should produce non-zero playing_handicap"
                assert len(p.strokes_received) > 0, "HANDICAP mode should produce strokes_received"

    async def test_should_use_custom_handicap_over_user_handicap(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que custom_handicap del enrollment tiene prioridad sobre user.handicap.

        Given: Jugador con handicap 15.0 pero custom_handicap 10.0 en su enrollment
        When: Se generan partidos en modo HANDICAP
        Then: El playing_handicap se calcula con el custom_handicap (10.0), no el user handicap (15.0)
        """
        # Arrange
        competition = await self._create_handicap_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )

        # Crear equipos manualmente para controlar enrollments
        player_a = UserId(uuid4())
        player_b = UserId(uuid4())

        team_assignment = TeamAssignmentEntity.create(
            competition_id=competition.id,
            mode=TeamAssignmentMode.MANUAL,
            team_a_player_ids=[player_a],
            team_b_player_ids=[player_b],
        )
        async with uow:
            await uow.team_assignments.add(team_assignment)

        # Player A: custom_handicap=10.0, user handicap=15.0
        enrollment_a = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=competition.id,
            user_id=player_a,
            status=EnrollmentStatus.APPROVED,
            tee_category=TeeCategory.AMATEUR_MALE,
        )
        enrollment_a.set_custom_handicap(Decimal("10.0"))
        async with uow:
            await uow.enrollments.add(enrollment_a)

        # Player B: no custom_handicap, user handicap=15.0
        enrollment_b = Enrollment(
            id=EnrollmentId.generate(),
            competition_id=competition.id,
            user_id=player_b,
            status=EnrollmentStatus.APPROVED,
            tee_category=TeeCategory.AMATEUR_MALE,
        )
        async with uow:
            await uow.enrollments.add(enrollment_b)

        # Mock golf course
        mock_gc = self._build_mock_golf_course([TeeCategory.AMATEUR_MALE])
        gc_repo.find_by_id = AsyncMock(return_value=mock_gc)

        # Mock user_repo: both users have handicap 15.0
        async def mock_find_user(uid):
            return self._build_mock_user(uid, 15.0)

        user_repo.find_by_id = AsyncMock(side_effect=mock_find_user)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act
        await use_case.execute(request, creator_id)

        # Assert
        matches = await uow.matches.find_by_round(round_entity.id)
        assert len(matches) == 1

        # Player A (custom_handicap=10.0) should have different PH than Player B (user handicap=15.0)
        match = matches[0]
        player_a_match = match.team_a_players[0]
        player_b_match = match.team_b_players[0]

        # With HI=10.0, CR=71.2, SR=128, Par=72 (sum of pars=72), allowance=100% (SINGLES default):
        # CH = 10.0 * (128/113) + (71.2 - 72) = 11.327... - 0.8 = 10.527...
        # PH = round(10.527...) = 11
        assert player_a_match.playing_handicap == 11

        # With HI=15.0, CR=71.2, SR=128, Par=72, allowance=100%:
        # CH = 15.0 * (128/113) + (71.2 - 72) = 16.991... - 0.8 = 16.191...
        # PH = round(16.191...) = 16
        assert player_b_match.playing_handicap == 16

        # Player A must have fewer strokes_received than Player B
        assert len(player_a_match.strokes_received) < len(player_b_match.strokes_received)

    async def test_should_raise_tee_category_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se lanza TeeCategoryNotFoundError cuando el tee del jugador no existe en el campo.

        Given: Jugador con tee_category CHAMPIONSHIP_FEMALE pero campo solo tiene AMATEUR_MALE
        When: Se generan partidos en modo HANDICAP
        Then: Se lanza TeeCategoryNotFoundError
        """
        # Arrange
        competition = await self._create_handicap_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )

        # Crear equipos con tee_category que NO esta en el campo
        await self._create_teams_and_enrollments_with_tees(
            uow, competition, 1, 1, TeeCategory.CHAMPIONSHIP_FEMALE
        )

        # Mock golf course con SOLO AMATEUR_MALE (no CHAMPIONSHIP_FEMALE)
        mock_gc = self._build_mock_golf_course([TeeCategory.AMATEUR_MALE])
        gc_repo.find_by_id = AsyncMock(return_value=mock_gc)

        # Mock user_repo
        async def mock_find_user(uid):
            return self._build_mock_user(uid, 12.0)

        user_repo.find_by_id = AsyncMock(side_effect=mock_find_user)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(TeeCategoryNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_when_no_golf_course_in_handicap_mode(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
        gc_repo: AsyncMock,
        user_repo: AsyncMock,
    ):
        """
        Verifica que se lanza ValueError cuando no hay campo de golf en modo HANDICAP.

        Given: Competicion HANDICAP sin campo de golf asociado (gc_repo retorna None)
        When: Se generan partidos
        Then: Se lanza ValueError con mensaje sobre requerir un campo de golf
        """
        # Arrange
        competition = await self._create_handicap_competition(uow, creator_id)
        round_entity = await self._create_round_pending_matches(
            uow, competition, golf_course_id, MatchFormat.SINGLES
        )
        await self._create_teams_and_enrollments_with_tees(uow, competition, 1, 1)

        # gc_repo.find_by_id retorna None (no hay campo de golf)
        gc_repo.find_by_id = AsyncMock(return_value=None)

        use_case = GenerateMatchesUseCase(
            uow=uow, golf_course_repository=gc_repo, user_repository=user_repo
        )
        request = GenerateMatchesRequestDTO(round_id=round_entity.id.value)

        # Act & Assert
        with pytest.raises(ValueError, match="campo de golf"):
            await use_case.execute(request, creator_id)
