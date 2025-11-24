# -*- coding: utf-8 -*-
"""Tests para CompleteCompetitionUseCase."""

import pytest
from datetime import date
from uuid import uuid4

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    CompleteCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.complete_competition_use_case import (
    CompleteCompetitionUseCase,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestCompleteCompetitionUseCase:
    """Suite de tests para el caso de uso CompleteCompetitionUseCase."""

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

    async def test_should_complete_competition_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se puede completar una competición en estado IN_PROGRESS.

        Given: Una competición en estado IN_PROGRESS
        When: El creador solicita completarla
        Then: Se completa correctamente y cambia a estado COMPLETED
        """
        # Arrange: Crear y llevar a IN_PROGRESS
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar, cerrar e iniciar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Completar competición
        complete_use_case = CompleteCompetitionUseCase(uow)
        complete_request = CompleteCompetitionRequestDTO(competition_id=created.id)
        response = await complete_use_case.execute(complete_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.status == "COMPLETED"
        assert response.completed_at is not None

        # Verificar que el estado se persistió correctamente
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "COMPLETED"
            assert competition.is_completed()

    async def test_should_raise_error_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta completar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        complete_use_case = CompleteCompetitionUseCase(uow)
        fake_id = uuid4()
        complete_request = CompleteCompetitionRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await complete_use_case.execute(complete_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede completar la competición.

        Given: Una competición en estado IN_PROGRESS
        When: Un usuario que NO es el creador intenta completarla
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear y llevar a IN_PROGRESS
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a IN_PROGRESS
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar completar con otro usuario
        complete_use_case = CompleteCompetitionUseCase(uow)
        complete_request = CompleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await complete_use_case.execute(complete_request, other_user_id)

        assert "Solo el creador puede completar" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_draft(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que no se puede completar una competición en DRAFT.

        Given: Una competición en estado DRAFT
        When: Se intenta completar
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear competición (queda en DRAFT)
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Intentar completar en DRAFT
        complete_use_case = CompleteCompetitionUseCase(uow)
        complete_request = CompleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await complete_use_case.execute(complete_request, creator_id)

        assert "No se puede completar una competición en estado DRAFT" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_closed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que no se puede completar una competición en CLOSED.

        Given: Una competición en estado CLOSED
        When: Se intenta completar
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear, activar y cerrar
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a CLOSED
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar completar en CLOSED
        complete_use_case = CompleteCompetitionUseCase(uow)
        complete_request = CompleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await complete_use_case.execute(complete_request, creator_id)

        assert "No se puede completar una competición en estado CLOSED" in str(exc_info.value)

    async def test_should_emit_domain_event_when_completed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se emite el evento CompetitionCompletedEvent.

        Given: Una competición en estado IN_PROGRESS
        When: Se completa correctamente
        Then: Se emite el evento de dominio
        """
        # Arrange: Crear y llevar a IN_PROGRESS
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a IN_PROGRESS
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Completar competición
        complete_use_case = CompleteCompetitionUseCase(uow)
        complete_request = CompleteCompetitionRequestDTO(competition_id=created.id)
        await complete_use_case.execute(complete_request, creator_id)

        # Assert: Verificar eventos
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            # Debe tener 5 eventos: Created, Activated, EnrollmentsClosed, Started, Completed
            assert len(events) == 5
            assert events[4].__class__.__name__ == "CompetitionCompletedEvent"
            assert events[4].competition_id == str(created.id)
