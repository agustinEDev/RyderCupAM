"""Tests para CancelCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CancelCompetitionRequestDTO,
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.cancel_competition_use_case import (
    CancelCompetitionUseCase,
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


class TestCancelCompetitionUseCase:
    """Suite de tests para el caso de uso CancelCompetitionUseCase."""

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

    async def test_should_cancel_competition_from_draft(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede cancelar una competición en estado DRAFT.

        Given: Una competición en estado DRAFT
        When: El creador solicita cancelarla
        Then: Se cancela correctamente y cambia a estado CANCELLED
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

        # Act: Cancelar competición
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(
            competition_id=created.id, reason="Mal tiempo"
        )
        response = await cancel_use_case.execute(cancel_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.status == "CANCELLED"
        assert response.reason == "Mal tiempo"
        assert response.cancelled_at is not None

        # Verificar que el estado se persistió correctamente
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition.status.value == "CANCELLED"
            assert competition.is_cancelled()

    async def test_should_cancel_competition_from_active(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede cancelar una competición en estado ACTIVE.

        Given: Una competición en estado ACTIVE
        When: El creador solicita cancelarla
        Then: Se cancela correctamente
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

        # Act: Cancelar competición
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(
            competition_id=created.id, reason="Falta de participantes"
        )
        response = await cancel_use_case.execute(cancel_request, creator_id)

        # Assert
        assert response.status == "CANCELLED"
        assert response.reason == "Falta de participantes"

    async def test_should_cancel_competition_from_in_progress(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede cancelar una competición en estado IN_PROGRESS.

        Given: Una competición en estado IN_PROGRESS
        When: El creador solicita cancelarla
        Then: Se cancela correctamente
        """
        # Arrange: Crear y llevar a IN_PROGRESS
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
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

        # Act: Cancelar competición
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(
            competition_id=created.id, reason="Condiciones del campo inadecuadas"
        )
        response = await cancel_use_case.execute(cancel_request, creator_id)

        # Assert
        assert response.status == "CANCELLED"

    async def test_should_cancel_without_reason(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede cancelar sin proporcionar razón.

        Given: Una competición existente
        When: Se cancela sin especificar razón
        Then: Se cancela correctamente con reason=None
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

        # Act: Cancelar sin razón
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(competition_id=created.id)
        response = await cancel_use_case.execute(cancel_request, creator_id)

        # Assert
        assert response.status == "CANCELLED"
        assert response.reason is None

    async def test_should_raise_error_when_competition_not_found(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta cancelar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        cancel_use_case = CancelCompetitionUseCase(uow)
        fake_id = uuid4()
        cancel_request = CancelCompetitionRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await cancel_use_case.execute(cancel_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self, uow: InMemoryUnitOfWork, creator_id: UserId, other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede cancelar la competición.

        Given: Una competición existente
        When: Un usuario que NO es el creador intenta cancelarla
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

        # Act: Intentar cancelar con otro usuario
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await cancel_use_case.execute(cancel_request, other_user_id)

        assert "Solo el creador puede cancelar" in str(exc_info.value)

    async def test_should_raise_error_when_already_completed(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se puede cancelar una competición COMPLETED.

        Given: Una competición en estado COMPLETED
        When: Se intenta cancelar
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear y completar competición
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

        # Act: Intentar cancelar
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await cancel_use_case.execute(cancel_request, creator_id)

        assert "No se puede cancelar una competición en estado final" in str(
            exc_info.value
        )

    async def test_should_raise_error_when_already_cancelled(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que no se puede cancelar una competición ya CANCELLED.

        Given: Una competición en estado CANCELLED
        When: Se intenta cancelar nuevamente
        Then: Se lanza CompetitionStateError
        """
        # Arrange: Crear y cancelar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Cancelar
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(competition_id=created.id)
        await cancel_use_case.execute(cancel_request, creator_id)

        # Act: Intentar cancelar nuevamente
        # Assert
        with pytest.raises(CompetitionStateError) as exc_info:
            await cancel_use_case.execute(cancel_request, creator_id)

        assert "No se puede cancelar una competición en estado final" in str(
            exc_info.value
        )

    async def test_should_emit_domain_event_when_cancelled(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se emite el evento CompetitionCancelledEvent.

        Given: Una competición en estado ACTIVE
        When: Se cancela correctamente
        Then: Se emite el evento de dominio con la razón
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

        # Act: Cancelar competición
        cancel_use_case = CancelCompetitionUseCase(uow)
        cancel_request = CancelCompetitionRequestDTO(
            competition_id=created.id, reason="Evento cancelado por el organizador"
        )
        await cancel_use_case.execute(cancel_request, creator_id)

        # Assert: Verificar eventos
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            events = competition.get_domain_events()

            # Debe tener 3 eventos: Created, Activated, Cancelled
            assert len(events) == 3
            assert events[2].__class__.__name__ == "CompetitionCancelledEvent"
            assert events[2].competition_id == str(created.id)
            assert events[2].reason == "Evento cancelado por el organizador"
