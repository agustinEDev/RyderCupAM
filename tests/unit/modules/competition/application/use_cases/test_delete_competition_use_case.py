"""Tests para DeleteCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    DeleteCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.delete_competition_use_case import (
    CompetitionNotDeletableError,
    CompetitionNotFoundError,
    DeleteCompetitionUseCase,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestDeleteCompetitionUseCase:
    """Suite de tests para el caso de uso DeleteCompetitionUseCase."""

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

    async def test_should_delete_competition_in_draft_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se puede eliminar una competición en estado DRAFT.

        Given: Una competición en estado DRAFT
        When: El creador solicita eliminarla
        Then: Se elimina correctamente y retorna confirmación
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Eliminar competición
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)
        response = await delete_use_case.execute(delete_request, creator_id)

        # Assert
        assert response.id == created.id
        assert response.name == "Ryder Cup 2025"
        assert response.deleted is True
        assert response.deleted_at is not None

        # Verificar que ya no existe en el repositorio
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            assert competition is None

    async def test_should_raise_error_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta eliminar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        delete_use_case = DeleteCompetitionUseCase(uow)
        fake_id = uuid4()
        delete_request = DeleteCompetitionRequestDTO(competition_id=fake_id)

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_user_is_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId,
        other_user_id: UserId
    ):
        """
        Verifica que solo el creador puede eliminar la competición.

        Given: Una competición existente
        When: Un usuario que NO es el creador intenta eliminarla
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Intentar eliminar con otro usuario
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await delete_use_case.execute(delete_request, other_user_id)

        assert "Solo el creador puede eliminar" in str(exc_info.value)

    async def test_should_raise_error_when_competition_is_not_draft(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que solo se pueden eliminar competiciones en estado DRAFT.

        Given: Una competición en estado ACTIVE
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError
        """
        # Arrange: Crear competición y activarla
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar la competición (cambiar a estado ACTIVE)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar eliminar competición ACTIVE
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "Solo se pueden eliminar competiciones en estado DRAFT" in str(exc_info.value)
        assert "Estado actual: ACTIVE" in str(exc_info.value)

    async def test_should_raise_error_when_trying_to_delete_in_progress_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que no se pueden eliminar competiciones en curso.

        Given: Una competición en estado IN_PROGRESS
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError
        """
        # Arrange: Crear competición y llevarla a IN_PROGRESS
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Llevar a IN_PROGRESS (DRAFT → ACTIVE → CLOSED → IN_PROGRESS)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            competition.close_enrollments()
            competition.start()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act: Intentar eliminar competición IN_PROGRESS
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "Solo se pueden eliminar competiciones en estado DRAFT" in str(exc_info.value)
        assert "Estado actual: IN_PROGRESS" in str(exc_info.value)

    async def test_should_raise_error_when_trying_to_delete_completed_competition(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que no se pueden eliminar competiciones completadas.

        Given: Una competición en estado COMPLETED
        When: El creador intenta eliminarla
        Then: Se lanza CompetitionNotDeletableError
        """
        # Arrange: Crear competición y llevarla a COMPLETED
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
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

        # Act: Intentar eliminar competición COMPLETED
        delete_use_case = DeleteCompetitionUseCase(uow)
        delete_request = DeleteCompetitionRequestDTO(competition_id=created.id)

        # Assert
        with pytest.raises(CompetitionNotDeletableError) as exc_info:
            await delete_use_case.execute(delete_request, creator_id)

        assert "Solo se pueden eliminar competiciones en estado DRAFT" in str(exc_info.value)
        assert "Estado actual: COMPLETED" in str(exc_info.value)
