# -*- coding: utf-8 -*-
"""Tests para GetCompetitionUseCase."""

import pytest
from datetime import date
from uuid import uuid4

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.get_competition_use_case import (
    GetCompetitionUseCase,
    CompetitionNotFoundError,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestGetCompetitionUseCase:
    """Suite de tests para el caso de uso GetCompetitionUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    async def test_should_get_competition_successfully(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se puede obtener una competición por su ID.

        Given: Una competición existente
        When: Se solicita por ID
        Then: Se retorna el DTO completo
        """
        # Arrange: Crear competición
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            adjacent_country_1="PT",
            handicap_type="PERCENTAGE",
            handicap_percentage=90
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act: Obtener competición
        get_use_case = GetCompetitionUseCase(uow)
        response = await get_use_case.execute(CompetitionId(created.id))

        # Assert
        assert response.id == created.id
        assert response.name == "Ryder Cup 2025"
        assert response.status == "DRAFT"
        assert response.creator_id == creator_id.value
        assert response.start_date == date(2025, 6, 1)
        assert response.end_date == date(2025, 6, 3)
        assert response.location["main_country"] == "ES"
        assert response.location["adjacent_country_1"] == "PT"
        assert response.handicap_settings["type"] == "PERCENTAGE"
        assert response.handicap_settings["percentage"] == 90

    async def test_should_get_competition_with_scratch_handicap(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se obtiene correctamente una competición con hándicap SCRATCH.

        Given: Competición con handicap SCRATCH
        When: Se solicita por ID
        Then: El DTO muestra percentage como None
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Scratch Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="FR",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        get_use_case = GetCompetitionUseCase(uow)
        response = await get_use_case.execute(CompetitionId(created.id))

        # Assert
        assert response.handicap_settings["type"] == "SCRATCH"
        assert response.handicap_settings["percentage"] is None

    async def test_should_raise_error_when_competition_not_found(
        self,
        uow: InMemoryUnitOfWork
    ):
        """
        Verifica que se lanza excepción si la competición no existe.

        Given: Un ID de competición inexistente
        When: Se intenta obtener
        Then: Se lanza CompetitionNotFoundError
        """
        # Arrange
        get_use_case = GetCompetitionUseCase(uow)
        fake_id = CompetitionId(uuid4())

        # Act & Assert
        with pytest.raises(CompetitionNotFoundError) as exc_info:
            await get_use_case.execute(fake_id)

        assert "No existe competición" in str(exc_info.value)

    async def test_should_get_competition_without_adjacent_countries(
        self,
        uow: InMemoryUnitOfWork,
        creator_id: UserId
    ):
        """
        Verifica que se obtiene correctamente una competición sin países adyacentes.

        Given: Competición solo con país principal
        When: Se solicita por ID
        Then: Los países adyacentes son None en el DTO
        """
        # Arrange
        create_use_case = CreateCompetitionUseCase(uow)
        create_request = CreateCompetitionRequestDTO(
            name="Single Country Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="IT",
            handicap_type="SCRATCH"
        )
        created = await create_use_case.execute(create_request, creator_id)

        # Act
        get_use_case = GetCompetitionUseCase(uow)
        response = await get_use_case.execute(CompetitionId(created.id))

        # Assert
        assert response.location["main_country"] == "IT"
        assert response.location["adjacent_country_1"] is None
        assert response.location["adjacent_country_2"] is None
