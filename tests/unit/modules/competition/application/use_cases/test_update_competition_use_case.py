# -*- coding: utf-8 -*-
"""Tests para UpdateCompetitionUseCase."""

import pytest
from datetime import date
from uuid import uuid4

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
    UpdateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.update_competition_use_case import (
    UpdateCompetitionUseCase,
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
    CompetitionNotEditableError,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestUpdateCompetitionUseCase:
    """Suite de tests para el caso de uso UpdateCompetitionUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    async def test_should_update_competition_name_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se puede actualizar el nombre de una competición.

        Given: Una competición existente en estado DRAFT
        When: Se actualiza solo el nombre
        Then: El nombre se actualiza correctamente
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Original Name",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Actualizar nombre
        update_use_case = UpdateCompetitionUseCase(uow)
        update_request = UpdateCompetitionRequestDTO(name="Updated Name")

        response = await update_use_case.execute(
            CompetitionId(created.id),
            update_request,
            creator_id
        )

        # Assert
        assert response.name == "Updated Name"
        assert response.id == created.id

        # Verificar en BD
        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.name) == "Updated Name"

    async def test_should_update_multiple_fields(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se pueden actualizar múltiples campos a la vez.

        Given: Una competición existente
        When: Se actualizan nombre, fechas y país
        Then: Todos los campos se actualizan correctamente
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Original",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        update_use_case = UpdateCompetitionUseCase(uow)
        update_request = UpdateCompetitionRequestDTO(
            name="Updated",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 3),
            main_country="FR"
        )

        await update_use_case.execute(
            CompetitionId(created.id),
            update_request,
            creator_id
        )

        # Assert
        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert str(competition.name) == "Updated"
        assert competition.dates.start_date == date(2025, 7, 1)
        assert competition.dates.end_date == date(2025, 7, 3)
        assert competition.location.main_country.value == "FR"

    async def test_should_update_handicap_from_scratch_to_percentage(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se puede cambiar el hándicap de SCRATCH a PERCENTAGE.

        Given: Competición con handicap SCRATCH
        When: Se actualiza a PERCENTAGE con 90%
        Then: El hándicap se actualiza correctamente
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        update_use_case = UpdateCompetitionUseCase(uow)
        update_request = UpdateCompetitionRequestDTO(
            handicap_type="PERCENTAGE",
            handicap_percentage=90
        )

        await update_use_case.execute(
            CompetitionId(created.id),
            update_request,
            creator_id
        )

        # Assert
        competition = await uow.competitions.find_by_id(CompetitionId(created.id))
        assert competition.handicap_settings.type.value == "PERCENTAGE"
        assert competition.handicap_settings.percentage == 90

    async def test_should_raise_error_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta actualizar
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        update_use_case = UpdateCompetitionUseCase(uow)
        fake_id = CompetitionId(uuid4())
        update_request = UpdateCompetitionRequestDTO(name="Test")

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await update_use_case.execute(fake_id, update_request, creator_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_raise_error_when_not_creator(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que solo el creador puede actualizar.

        Given: Una competición creada por user A
        When: User B intenta actualizar
        Then: Se lanza NotCompetitionCreatorError
        """
        # Arrange: Crear con creator_id
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act & Assert: Intentar actualizar con otro usuario
        update_use_case = UpdateCompetitionUseCase(uow)
        other_user = UserId(uuid4())
        update_request = UpdateCompetitionRequestDTO(name="Hacked")

        with pytest.raises(NotCompetitionCreatorError) as exc_info:
            await update_use_case.execute(
                CompetitionId(created.id),
                update_request,
                other_user
            )

        assert "Solo el creador" in str(exc_info.value)

    async def test_should_raise_error_when_not_in_draft_state(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que solo se puede actualizar en estado DRAFT.

        Given: Una competición activada (ACTIVE)
        When: Se intenta actualizar
        Then: Se lanza CompetitionNotEditableError
        """
        # Arrange: Crear y activar competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Activar la competición (cambiar a ACTIVE)
        async with uow:
            competition = await uow.competitions.find_by_id(CompetitionId(created.id))
            competition.activate()
            await uow.competitions.update(competition)
            await uow.commit()

        # Act & Assert: Intentar actualizar
        update_use_case = UpdateCompetitionUseCase(uow)
        update_request = UpdateCompetitionRequestDTO(name="Cannot Update")

        with pytest.raises(CompetitionNotEditableError) as exc_info:
            await update_use_case.execute(
                CompetitionId(created.id),
                update_request,
                creator_id
            )

        assert "Solo se permite en estado DRAFT" in str(exc_info.value)

    async def test_should_raise_error_when_percentage_missing(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si se pone PERCENTAGE sin porcentaje.

        Given: Actualización con handicap_type PERCENTAGE
        When: No se proporciona handicap_percentage
        Then: Se lanza ValueError
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act & Assert
        update_use_case = UpdateCompetitionUseCase(uow)
        update_request = UpdateCompetitionRequestDTO(
            handicap_type="PERCENTAGE"
            # handicap_percentage falta!
        )

        with pytest.raises(ValueError) as exc_info:
            await update_use_case.execute(
                CompetitionId(created.id),
                update_request,
                creator_id
            )

        assert "handicap_percentage es requerido" in str(exc_info.value)

    async def test_should_commit_transaction(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que la transacción se hace commit correctamente.

        Given: Una actualización válida
        When: Se ejecuta el caso de uso
        Then: Se llama a commit() en el UoW
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Test",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        update_use_case = UpdateCompetitionUseCase(uow)
        update_request = UpdateCompetitionRequestDTO(name="Updated")

        await update_use_case.execute(
            CompetitionId(created.id),
            update_request,
            creator_id
        )

        # Assert
        assert uow.committed is True
