"""Tests para StartCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    StartCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.start_competition_use_case import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    StartCompetitionUseCase,
)
from src.modules.competition.domain.entities.competition import CompetitionStateError
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestStartCompetitionUseCase:
    """Suite de tests para el caso de uso StartCompetitionUseCase."""

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

    async def test_should_start_competition_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede iniciar una competición en estado CLOSED.

        Given: Una competición en estado CLOSED
        When: El creador solicita iniciarla
        Then: Se inicia correctamente y cambia a estado IN_PROGRESS
        """
        # Arrange: Crear, activar y cerrar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar y cerrar inscripciones
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Iniciar competición
        start_use_case = StartCompetitionUseCase(uow)
        start_request = StartCompetitionRequestDTO(competition_id=created.id)
        response = await start_use_case.execute(start_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.status == "IN_PROGRESS"
        assert response.started_at is not None

        # Verificar que el estado se persistió correctamente
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "IN_PROGRESS"
            assert competition.is_in_progress()

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta iniciar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        start_use_case = StartCompetitionUseCase(uow)
        fake_id = uuid4()
        start_request = StartCompetitionRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await start_use_case.execute(start_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede iniciar la competición.

        Given: Una competición en estado CLOSED
        When: Un usuario que NO es el creador intenta iniciarla
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear, activar y cerrar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar y cerrar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar iniciar con otro usuario
        start_use_case = StartCompetitionUseCase(uow)
        start_request = StartCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await start_use_case.execute(start_request, other_user_id)

        assert "Solo el creador puede iniciar" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_draft(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se puede iniciar una competición en DRAFT.

        Given: Una competición en estado DRAFT
        When: Se intenta iniciar
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear competición (queda en DRAFT)
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Intentar iniciar en DRAFT
        start_use_case = StartCompetitionUseCase(uow)
        start_request = StartCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await start_use_case.execute(start_request, creator_id)

        assert "No se puede iniciar una competición en estado DRAFT" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_active(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se puede iniciar una competición en ACTIVE.

        Given: Una competición en estado ACTIVE
        When: Se intenta iniciar
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear y activar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar iniciar en ACTIVE
        start_use_case = StartCompetitionUseCase(uow)
        start_request = StartCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await start_use_case.execute(start_request, creator_id)

        assert "No se puede iniciar una competición en estado ACTIVE" in str(exc_info.value)

    async def test_should_emit_domain_event_when_started(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se emite el evento CompetitionStartedEvent.

        Given: Una competición en estado CLOSED
        When: Se inicia correctamente
        Then: Se emite el evento de dominio
        """
        # Arrange: Crear, activar y cerrar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar y cerrar
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Iniciar competición
        start_use_case = StartCompetitionUseCase(uow)
        start_request = StartCompetitionRequestDTO(competition_id=created.id)
        await start_use_case.execute(start_request, creator_id)

        # Assert: Verificar eventos
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            # Debe tener 4 eventos: Created, Activated, EnrollmentsClosed, Started
            assert len(events) == 4
            assert events[3].__class__.__name__ == "CompetitionStartedEvent"
            assert events[3].competition_id == str(created.id)
