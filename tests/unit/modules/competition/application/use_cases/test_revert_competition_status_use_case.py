"""Tests para RevertCompetitionStatusUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    RevertCompetitionStatusRequestDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.revert_competition_status_use_case import (
    RevertCompetitionStatusUseCase,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.events.competition_reverted_to_closed_event import (
    CompetitionRevertedToClosedEvent,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class TestRevertCompetitionStatusUseCase:
    """Suite de tests para el caso de uso RevertCompetitionStatusUseCase."""

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

    async def _create_in_progress_competition(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """Helper: crea una competición en estado IN_PROGRESS."""
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
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        return created

    async def test_should_revert_competition_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede revertir una competición de IN_PROGRESS a CLOSED.

        Given: Una competición en estado IN_PROGRESS
        When: El creador solicita revertirla
        Then: Se revierte correctamente y cambia a estado CLOSED
        """
        created = await self._create_in_progress_competition(uow, creator_id)

        use_case = RevertCompetitionStatusUseCase(uow)
        request = RevertCompetitionStatusRequestDTO(competition_id=created.id)
        response = await use_case.execute(request, creator_id)

        assert response.id == created.id
        assert response.status == "CLOSED"
        assert response.reverted_at is not None

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "CLOSED"

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Un ID de competición inexistente
        When: Se intenta revertir
        Then: Se lanza CompetitionNotFoundError
        """
        use_case = RevertCompetitionStatusUseCase(uow)
        request = RevertCompetitionStatusRequestDTO(competition_id=uuid4())

        with pytest.raises(CompetitionNotFoundError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_error_when_user_is_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Given: Una competición en estado IN_PROGRESS
        When: Un usuario que NO es el creador intenta revertirla
        Then: Se lanza NotCompetitionCreatorError
        """
        created = await self._create_in_progress_competition(uow, creator_id)

        use_case = RevertCompetitionStatusUseCase(uow)
        request = RevertCompetitionStatusRequestDTO(competition_id=created.id)

        with pytest.raises(NotCompetitionCreatorError):
            await use_case.execute(request, other_user_id)

    async def test_should_raise_error_when_competition_is_closed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición en estado CLOSED
        When: Se intenta revertir
        Then: Se lanza CompetitionStateError (ya está en CLOSED)
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
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        use_case = RevertCompetitionStatusUseCase(uow)
        request = RevertCompetitionStatusRequestDTO(competition_id=created.id)

        with pytest.raises(CompetitionStateError):
            await use_case.execute(request, creator_id)

    async def test_should_raise_error_when_competition_is_completed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición en estado COMPLETED (terminal)
        When: Se intenta revertir
        Then: Se lanza CompetitionStateError
        """
        created = await self._create_in_progress_competition(uow, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.complete()
            await uow.competitions.update(competition)
            await uow.commit()

        use_case = RevertCompetitionStatusUseCase(uow)
        request = RevertCompetitionStatusRequestDTO(competition_id=created.id)

        with pytest.raises(CompetitionStateError):
            await use_case.execute(request, creator_id)

    async def test_should_emit_domain_event_when_reverted(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Given: Una competición en estado IN_PROGRESS
        When: Se revierte correctamente
        Then: Se emite CompetitionRevertedToClosedEvent
        """
        created = await self._create_in_progress_competition(uow, creator_id)

        use_case = RevertCompetitionStatusUseCase(uow)
        request = RevertCompetitionStatusRequestDTO(competition_id=created.id)
        await use_case.execute(request, creator_id)

        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            reverted_events = [
                e for e in events if isinstance(e, CompetitionRevertedToClosedEvent)
            ]
            assert len(reverted_events) == 1
            assert reverted_events[0].competition_id == str(created.id)
