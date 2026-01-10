"""Tests para CreateCompetitionUseCase."""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CompetitionAlreadyExistsError,
    CreateCompetitionUseCase,
)
from src.modules.competition.domain.services.location_builder import InvalidCountryError
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestCreateCompetitionUseCase:
    """Suite de tests para el caso de uso CreateCompetitionUseCase."""

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def creator_id(self) -> UserId:
        """Fixture que proporciona un ID de usuario creador."""
        return UserId(uuid4())

    async def test_should_create_competition_successfully(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que una competición se crea correctamente con datos válidos.

        Given: Datos válidos de competición con país principal España
        When: Se ejecuta el caso de uso
        Then: La competición se crea en estado DRAFT y se persiste
        """
        # Arrange
        use_case = CreateCompetitionUseCase(uow)
        request_dto = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
            max_players=24,
            team_assignment="MANUAL",
            team_1_name="Europa",
            team_2_name="USA",
        )

        # Act
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        # 1. Verificar respuesta del DTO
        assert response.name == "Ryder Cup 2025"
        assert response.status == "DRAFT"
        assert response.creator_id == creator_id.value
        assert response.start_date == date(2025, 6, 1)
        assert response.end_date == date(2025, 6, 3)
        assert response.id is not None
        assert response.team_1_name == "Europa"
        assert response.team_2_name == "USA"

        # 2. Verificar que se guardó en la BD
        competitions = await uow.competitions.find_all()
        assert len(competitions) == 1
        assert competitions[0].name.value == "Ryder Cup 2025"
        assert competitions[0].team_1_name == "Europa"
        assert competitions[0].team_2_name == "USA"

    async def test_should_create_competition_with_adjacent_countries(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede crear una competición con países adyacentes.

        Given: Datos con país principal España y adyacentes Portugal y Francia
        When: Se ejecuta el caso de uso
        Then: La competición se crea con los 3 países correctamente
        """
        # Arrange
        use_case = CreateCompetitionUseCase(uow)
        request_dto = CreateCompetitionRequestDTO(
            name="Iberian Cup 2025",
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 3),
            main_country="ES",
            adjacent_country_1="PT",
            adjacent_country_2="FR",
            handicap_type="PERCENTAGE",
            handicap_percentage=90,
        )

        # Act
        response = await use_case.execute(request_dto, creator_id)

        # Assert
        assert response.name == "Iberian Cup 2025"
        competitions = await uow.competitions.find_all()
        assert len(competitions) == 1

        # Verificar que Location tiene los 3 países
        competition = competitions[0]
        assert competition.location.main_country.value == "ES"
        assert competition.location.adjacent_country_1.value == "PT"
        assert competition.location.adjacent_country_2.value == "FR"

    async def test_should_raise_error_when_name_already_exists(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si el nombre ya existe.

        Given: Una competición existente con nombre "Ryder Cup 2025"
        When: Se intenta crear otra con el mismo nombre
        Then: Se lanza CompetitionAlreadyExistsError
        """
        # Arrange: Crear competición existente
        use_case = CreateCompetitionUseCase(uow)
        existing_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )
        await use_case.execute(existing_request, creator_id)

        # Act & Assert: Intentar crear otra con el mismo nombre
        duplicate_request = CreateCompetitionRequestDTO(
            name="Ryder Cup 2025",  # Mismo nombre
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 3),
            main_country="FR",
            handicap_type="SCRATCH",
        )

        with pytest.raises(CompetitionAlreadyExistsError) as exc_info:
            await use_case.execute(duplicate_request, creator_id)

        assert "Ya existe una competición con el nombre 'Ryder Cup 2025'" in str(exc_info.value)

    async def test_should_raise_error_when_country_does_not_exist(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si el país no existe.

        Given: Datos con un país inexistente "XX"
        When: Se ejecuta el caso de uso
        Then: Se lanza InvalidCountryError
        """
        # Arrange
        use_case = CreateCompetitionUseCase(uow)
        request_dto = CreateCompetitionRequestDTO(
            name="Invalid Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="XX",  # País inexistente
            handicap_type="SCRATCH",
        )

        # Act & Assert
        with pytest.raises(InvalidCountryError) as exc_info:
            await use_case.execute(request_dto, creator_id)

        assert "El país con código 'XX' no existe" in str(exc_info.value)

    async def test_should_raise_error_when_adjacent_country_not_adjacent(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se lanza excepción si el país adyacente no es realmente adyacente.

        Given: España como principal e Italia como adyacente (no son fronterizos)
        When: Se ejecuta el caso de uso
        Then: Se lanza InvalidCountryError
        """
        # Arrange
        use_case = CreateCompetitionUseCase(uow)
        request_dto = CreateCompetitionRequestDTO(
            name="Invalid Adjacency Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            adjacent_country_1="IT",  # Italia no es adyacente a España
            handicap_type="SCRATCH",
        )

        # Act & Assert
        with pytest.raises(InvalidCountryError) as exc_info:
            await use_case.execute(request_dto, creator_id)

        assert "no es adyacente" in str(exc_info.value)

    async def test_should_create_with_percentage_handicap(
        self, uow: InMemoryUnitOfWork, creator_id: UserId
    ):
        """
        Verifica que se puede crear competición con hándicap por porcentaje.

        Given: Datos con handicap_type PERCENTAGE y handicap_percentage 95
        When: Se ejecuta el caso de uso
        Then: La competición se crea con hándicap configurado
        """
        # Arrange
        use_case = CreateCompetitionUseCase(uow)
        request_dto = CreateCompetitionRequestDTO(
            name="Percentage Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="FR",
            handicap_type="PERCENTAGE",
            handicap_percentage=95,
        )

        # Act
        await use_case.execute(request_dto, creator_id)

        # Assert
        competitions = await uow.competitions.find_all()
        competition = competitions[0]
        assert competition.handicap_settings.type.value == "PERCENTAGE"
        assert competition.handicap_settings.percentage == 95

    async def test_should_commit_transaction(self, uow: InMemoryUnitOfWork, creator_id: UserId):
        """
        Verifica que la transacción se hace commit correctamente.

        Given: Una solicitud válida de creación
        When: Se ejecuta el caso de uso
        Then: Se llama a commit() en el UoW
        """
        # Arrange
        use_case = CreateCompetitionUseCase(uow)
        request_dto = CreateCompetitionRequestDTO(
            name="Commit Test Cup",
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 3),
            main_country="ES",
            handicap_type="SCRATCH",
        )

        # Act
        await use_case.execute(request_dto, creator_id)

        # Assert
        assert uow.committed is True
