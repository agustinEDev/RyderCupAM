"""Tests para CloseEnrollmentsUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CloseEnrollmentsRequestDTO,
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.close_enrollments_use_case import (
    CloseEnrollmentsUseCase,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestCloseEnrollmentsUseCase:
    """Suite de tests para el caso de uso CloseEnrollmentsUseCase."""

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

    async def test_should_close_enrollments_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se pueden cerrar inscripciones de una competición ACTIVE.

        Given: Una competición en estado ACTIVE
        When: El creador solicita cerrar inscripciones
        Then: Se cierran correctamente y cambia a estado CLOSED
        """
        # Arrange: Crear y activar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Cerrar inscripciones
        close_use_case = CloseEnrollmentsUseCase(uow)
        close_request = CloseEnrollmentsRequestDTO(competition_id=created.id)
        response = await close_use_case.execute(close_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.status == "CLOSED"
        assert response.total_enrollments == 0  # No hay inscripciones
        assert response.closed_at is not None

        # Verificar que el estado se persistió correctamente
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "CLOSED"

    async def test_should_raise_error_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta cerrar inscripciones
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        close_use_case = CloseEnrollmentsUseCase(uow)
        fake_id = uuid4()
        close_request = CloseEnrollmentsRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await close_use_case.execute(close_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede cerrar inscripciones.

        Given: Una competición en estado ACTIVE
        When: Un usuario que NO es el creador intenta cerrar inscripciones
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear y activar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar cerrar con otro usuario
        close_use_case = CloseEnrollmentsUseCase(uow)
        close_request = CloseEnrollmentsRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await close_use_case.execute(close_request, other_user_id)

        assert "Solo el creador puede cerrar las inscripciones" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_draft(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que no se pueden cerrar inscripciones si está en DRAFT.

        Given: Una competición en estado DRAFT
        When: Se intenta cerrar inscripciones
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

        # Act: Intentar cerrar inscripciones en DRAFT
        close_use_case = CloseEnrollmentsUseCase(uow)
        close_request = CloseEnrollmentsRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await close_use_case.execute(close_request, creator_id)

        assert "No se pueden cerrar inscripciones en estado DRAFT" in str(exc_info.value)

    async def test_should_raise_error_when_already_closed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que no se pueden cerrar inscripciones si ya están cerradas.

        Given: Una competición en estado CLOSED
        When: Se intenta cerrar inscripciones nuevamente
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear, activar y cerrar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar y cerrar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar cerrar nuevamente
        close_use_case = CloseEnrollmentsUseCase(uow)
        close_request = CloseEnrollmentsRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await close_use_case.execute(close_request, creator_id)

        assert "No se pueden cerrar inscripciones en estado CLOSED" in str(exc_info.value)

    async def test_should_emit_domain_event_when_closed(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se emite el evento CompetitionEnrollmentsClosedEvent.

        Given: Una competición en estado ACTIVE
        When: Se cierran las inscripciones correctamente
        Then: Se emite el evento de dominio
        """
        # Arrange: Crear y activar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Cerrar inscripciones
        close_use_case = CloseEnrollmentsUseCase(uow)
        close_request = CloseEnrollmentsRequestDTO(competition_id=created.id)
        await close_use_case.execute(close_request, creator_id)

        # Assert: Verificar eventos
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            # Debe tener 3 eventos: Created, Activated, EnrollmentsClosed
            assert len(events) == 3
            assert events[2].__class__.__name__ == "CompetitionEnrollmentsClosedEvent"
            assert events[2].competition_id == str(created.id)
            assert events[2].total_enrollments == 0
