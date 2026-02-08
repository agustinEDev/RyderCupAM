"""Tests para UpdateRoundUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.round_match_dto import (
    UpdateRoundRequestDTO,
)
from src.modules.competition.application.use_cases.update_round_use_case import (
    DuplicateSessionError,
    GolfCourseNotInCompetitionError,
    NotCompetitionCreatorError,
    RoundNotFoundError,
    RoundNotModifiableError,
    UpdateRoundUseCase,
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


class TestUpdateRoundUseCase:
    """Suite de tests para el caso de uso UpdateRoundUseCase."""

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

    async def test_should_update_round_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que se actualiza una ronda correctamente.

        Given: Una ronda en estado PENDING_TEAMS con session_type MORNING
        When: El creador cambia session_type a AFTERNOON
        Then: La ronda se actualiza correctamente
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        use_case = UpdateRoundUseCase(uow=uow)
        request = UpdateRoundRequestDTO(
            round_id=round_entity.id.value,
            session_type="AFTERNOON",
        )

        # Act
        response = await use_case.execute(request, creator_id)

        # Assert
        assert response.id == round_entity.id.value
        assert response.status == "PENDING_TEAMS"
        assert response.updated_at is not None

    async def test_should_fail_when_round_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
    ):
        """
        Verifica que se lanza error cuando la ronda no existe.

        Given: Un ID de ronda que no existe
        When: Se intenta actualizar la ronda
        Then: Se lanza RoundNotFoundError
        """
        # Arrange
        use_case = UpdateRoundUseCase(uow=uow)
        request = UpdateRoundRequestDTO(
            round_id=uuid4(),
            session_type="AFTERNOON",
        )

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
        Verifica que solo el creador puede actualizar rondas.

        Given: Una ronda creada por un usuario
        When: Otro usuario intenta actualizar la ronda
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        use_case = UpdateRoundUseCase(uow=uow)
        request = UpdateRoundRequestDTO(
            round_id=round_entity.id.value,
            session_type="AFTERNOON",
        )

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
        Verifica que no se puede actualizar una ronda en estado SCHEDULED.

        Given: Una ronda en estado SCHEDULED (tras mark_teams_assigned y mark_matches_generated)
        When: Se intenta actualizar la ronda
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

        use_case = UpdateRoundUseCase(uow=uow)
        request = UpdateRoundRequestDTO(
            round_id=round_entity.id.value,
            session_type="AFTERNOON",
        )

        # Act & Assert
        with pytest.raises(RoundNotModifiableError):
            await use_case.execute(request, creator_id)

    async def test_should_fail_when_golf_course_not_in_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        golf_course_id: GolfCourseId,
    ):
        """
        Verifica que no se puede cambiar a un campo de golf no asociado.

        Given: Una ronda existente en una competicion con un campo asociado
        When: Se intenta cambiar el campo a uno no asociado a la competicion
        Then: Se lanza GolfCourseNotInCompetitionError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )
        round_entity = await self._create_round_for_competition(uow, competition, golf_course_id)

        other_golf_course_id = GolfCourseId(uuid4())

        use_case = UpdateRoundUseCase(uow=uow)
        request = UpdateRoundRequestDTO(
            round_id=round_entity.id.value,
            golf_course_id=other_golf_course_id.value,
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
        Verifica que no se puede cambiar a un session_type que ya existe en esa fecha.

        Given: Dos rondas, MORNING y AFTERNOON, en la misma fecha
        When: Se intenta cambiar la AFTERNOON a MORNING
        Then: Se lanza DuplicateSessionError
        """
        # Arrange
        competition = await self._create_closed_competition_with_course(
            uow, creator_id, golf_course_id
        )

        # Crear ronda MORNING
        await self._create_round_for_competition(
            uow,
            competition,
            golf_course_id,
            session_type=SessionType.MORNING,
        )

        # Crear ronda AFTERNOON
        afternoon_round = await self._create_round_for_competition(
            uow,
            competition,
            golf_course_id,
            session_type=SessionType.AFTERNOON,
        )

        # Intentar cambiar AFTERNOON a MORNING (duplicado)
        use_case = UpdateRoundUseCase(uow=uow)
        request = UpdateRoundRequestDTO(
            round_id=afternoon_round.id.value,
            session_type="MORNING",
        )

        # Act & Assert
        with pytest.raises(DuplicateSessionError):
            await use_case.execute(request, creator_id)
