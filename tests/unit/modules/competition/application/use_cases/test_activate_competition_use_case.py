"""Tests para ActivateCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    ActivateCompetitionRequestDTO,
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.activate_competition_use_case import (
    ActivateCompetitionUseCase,
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


class TestActivateCompetitionUseCase:
    """Suite de tests para el caso de uso ActivateCompetitionUseCase."""

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

    async def test_should_activate_competition_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede activar una competición en estado DRAFT.

        Given: Una competición en estado DRAFT
        When: El creador solicita activarla
        Then: Se activa correctamente y cambia a estado ACTIVE
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Activar competición
        activate_use_case = ActivateCompetitionUseCase(uow)
        activate_request = ActivateCompetitionRequestDTO(competition_id=created.id)
        response = await activate_use_case.execute(activate_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.status == "ACTIVE"
        assert response.activated_at is not None

        # Verificar que el estado se persistió correctamente
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "ACTIVE"
            assert competition.is_active()

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta activar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        activate_use_case = ActivateCompetitionUseCase(uow)
        fake_id = uuid4()
        activate_request = ActivateCompetitionRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await activate_use_case.execute(activate_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede activar la competición.

        Given: Una competición existente
        When: Un usuario que NO es el creador intenta activarla
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Intentar activar con otro usuario
        activate_use_case = ActivateCompetitionUseCase(uow)
        activate_request = ActivateCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await activate_use_case.execute(activate_request, other_user_id)

        assert "Solo el creador puede activar" in str(exc_info.value)

    async def test_should_raise_error_when_already_active(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se puede activar una competición ya activa.

        Given: Una competición en estado ACTIVE
        When: Se intenta activar nuevamente
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

        # Primera activación (exitosa)
        activate_use_case = ActivateCompetitionUseCase(uow)
        activate_request = ActivateCompetitionRequestDTO(competition_id=created.id)
        await activate_use_case.execute(activate_request, creator_id)

        # Act: Intentar activar nuevamente
        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await activate_use_case.execute(activate_request, creator_id)

        assert "No se puede activar una competición en estado ACTIVE" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_completed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se puede activar una competición completada.

        Given: Una competición en estado COMPLETED
        When: Se intenta activar
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear competición y llevarla a COMPLETED
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a COMPLETED
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            competition.start()
            competition.complete()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar activar competición COMPLETED
        activate_use_case = ActivateCompetitionUseCase(uow)
        activate_request = ActivateCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await activate_use_case.execute(activate_request, creator_id)

        assert "No se puede activar una competición en estado COMPLETED" in str(exc_info.value)

    async def test_should_emit_domain_event_when_activated(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se emite el evento CompetitionActivatedEvent.

        Given: Una competición en estado DRAFT
        When: Se activa correctamente
        Then: Se emite el evento de dominio
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Activar competición
        activate_use_case = ActivateCompetitionUseCase(uow)
        activate_request = ActivateCompetitionRequestDTO(competition_id=created.id)
        await activate_use_case.execute(activate_request, creator_id)

        # Assert: Verificar evento
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            # Debe tener 2 eventos: CompetitionCreatedEvent y CompetitionActivatedEvent
            assert len(events) == 2
            assert events[1].__class__.__name__ == "CompetitionActivatedEvent"
            assert events[1].competition_id == str(created.id)
