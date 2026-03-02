"""Tests para ReopenEnrollmentsUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    ReopenEnrollmentsRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.reopen_enrollments_use_case import (
    ReopenEnrollmentsUseCase,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.events.competition_enrollments_reopened_event import (
    CompetitionEnrollmentsReopenedEvent,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class TestReopenEnrollmentsUseCase:
    """Suite de tests para el caso de uso ReopenEnrollmentsUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    @pytest.fixture
    def other_user_id(self) -> UserId:
        """Fixture que proporciona un ID de otro usuario (no creador)."""
        return UserId(uuid4())

    async def _create_closed_competition(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """Helper: crea una competición en estado CLOSED."""
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        return created

    async def test_should_reopen_enrollments_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se pueden reabrir inscripciones de CLOSED a ACTIVE.

        Given: Una competición en estado CLOSED
        When: El creador solicita reabrir inscripciones
        Then: Se reabre correctamente y cambia a estado ACTIVE
        """
        created = await self._create_closed_competition(uow, creator_id)

        use_case = ReopenEnrollmentsUseCase(uow)
        request = ReopenEnrollmentsRequestDTO(competition_id=created.id)
        response = await use_case.execute(request, creator_id)

        assert response.id == created.id
        assert response.status == "ACTIVE"
        assert response.reopened_at is not None

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "ACTIVE"
            assert competition.allows_enrollments()

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un ID de competición inexistente
        When: Se intenta reabrir inscripciones
        Then: Se lanza CompetitionNotFoundError
        """
        use_case = ReopenEnrollmentsUseCase(uow)
        request = ReopenEnrollmentsRequestDTO(competition_id=uuid4())

        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_error_when_user_is_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Given: Una competición en estado CLOSED
        When: Un usuario que NO es el creador intenta reabrir
        Then: Se lanza NotCompetitionCreatorError
        """
        created = await self._create_closed_competition(uow, creator_id)

        use_case = ReopenEnrollmentsUseCase(uow)
        request = ReopenEnrollmentsRequestDTO(competition_id=created.id)

        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_raise_error_when_competition_is_active(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición en estado ACTIVE
        When: Se intenta reabrir inscripciones
        Then: Se lanza CompetitionStateError (ya está en ACTIVE)
        """
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        use_case = ReopenEnrollmentsUseCase(uow)
        request = ReopenEnrollmentsRequestDTO(competition_id=created.id)

        with pytest.raises(CompetitionStateError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_error_when_competition_is_in_progress(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición en estado IN_PROGRESS
        When: Se intenta reabrir inscripciones
        Then: Se lanza CompetitionStateError (no puede ir a ACTIVE desde IN_PROGRESS)
        """
        created = await self._create_closed_competition(uow, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        use_case = ReopenEnrollmentsUseCase(uow)
        request = ReopenEnrollmentsRequestDTO(competition_id=created.id)

        with pytest.raises(CompetitionStateError):
            await use_case.execute(request, creator_id)

    async def test_should_emit_domain_event_when_reopened(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición en estado CLOSED
        When: Se reabren inscripciones correctamente
        Then: Se emite CompetitionEnrollmentsReopenedEvent
        """
        created = await self._create_closed_competition(uow, creator_id)

        use_case = ReopenEnrollmentsUseCase(uow)
        request = ReopenEnrollmentsRequestDTO(competition_id=created.id)
        await use_case.execute(request, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            reopened_events = [
                e for e in events if isinstance(e, CompetitionEnrollmentsReopenedEvent)
            ]
            assert len(reopened_events) == 1
            assert reopened_events[0].competition_id == str(created.id)
