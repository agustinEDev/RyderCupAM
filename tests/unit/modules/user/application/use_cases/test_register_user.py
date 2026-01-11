from unittest.mock import AsyncMock

import pytest

from src.modules.user.application.dto.user_dto import RegisterUserRequestDTO
from src.modules.user.application.use_cases.register_user_use_case import (
    RegisterUserUseCase,
)
from src.modules.user.domain.errors.user_errors import UserAlreadyExistsError
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

# Marcar todos los tests de este fichero para que se ejecuten con asyncio
pytestmark = pytest.mark.asyncio


class TestRegisterUserUseCase:
    """
    Suite de tests para el caso de uso RegisterUserUseCase.
    """

    @pytest.fixture
    def uow(self) -> InMemoryUnitOfWork:
        """Fixture que proporciona una Unit of Work en memoria para cada test."""
        return InMemoryUnitOfWork()

    @pytest.fixture
    def country_repository(self):
        """Fixture que proporciona un mock de CountryRepository."""
        mock_repo = AsyncMock()
        # Por defecto, todos los country codes son válidos
        mock_repo.exists.return_value = True
        return mock_repo

    async def test_should_register_user_successfully(
        self, uow: InMemoryUnitOfWork, country_repository
    ):
        """
        Verifica que un usuario se registra correctamente cuando los datos son válidos
        y el email no existe previamente.
        """
        # Arrange
        use_case = RegisterUserUseCase(uow, country_repository)
        request_dto = RegisterUserRequestDTO(
            email="test.user@example.com",
            password="V@l1dP@ss123!",
            first_name="Test",
            last_name="User",
        )

        # Act
        user_response = await use_case.execute(request_dto)

        # Assert
        # 1. Verificar que la respuesta del DTO es correcta
        assert user_response.email == request_dto.email
        assert user_response.first_name == request_dto.first_name
        assert user_response.id is not None

        # 2. Verificar que el usuario fue realmente guardado en la persistencia
        async with uow:
            user_id_vo = UserId(user_response.id)
            saved_user = await uow.users.find_by_id(user_id_vo)
            assert saved_user is not None
            assert str(saved_user.email) == request_dto.email

    async def test_should_raise_error_when_email_already_exists(
        self, uow: InMemoryUnitOfWork, country_repository
    ):
        """
        Verifica que se lanza la excepción UserAlreadyExistsError si se intenta
        registrar un usuario con un email que ya existe.
        """
        # Arrange: Primero, creamos un usuario existente
        use_case = RegisterUserUseCase(uow, country_repository)
        existing_user_request = RegisterUserRequestDTO(
            email="existing.user@example.com",
            password="V@l1dP@ss123!",
            first_name="Existing",
            last_name="User",
        )
        await use_case.execute(existing_user_request)

        # Ahora, intentamos registrar otro usuario con el MISMO email
        new_request_dto = RegisterUserRequestDTO(
            email="existing.user@example.com",
            password="An0th3rV@l1dP@ss!",
            first_name="Another",
            last_name="User",
        )

        # Act & Assert
        with pytest.raises(UserAlreadyExistsError, match="ya está registrado"):
            await use_case.execute(new_request_dto)

    async def test_should_register_user_with_manual_handicap_when_rfeg_returns_none(
        self, uow: InMemoryUnitOfWork, country_repository
    ):
        """
        Verifica que se puede registrar un usuario con hándicap manual
        cuando RFEG devuelve None.
        """
        # Arrange
        from src.modules.user.infrastructure.external.mock_handicap_service import (
            MockHandicapService,
        )

        # Servicio que siempre devuelve None (usuario no encontrado en RFEG)
        handicap_service = MockHandicapService(default=None)
        use_case = RegisterUserUseCase(uow, country_repository, handicap_service)

        request_dto = RegisterUserRequestDTO(
            email="test.user@example.com",
            password="V@l1dP@ss123!",
            first_name="Test",
            last_name="User",
            manual_handicap=15.5,
        )

        # Act
        user_response = await use_case.execute(request_dto)

        # Assert
        assert user_response.handicap == pytest.approx(15.5)

    async def test_should_prefer_rfeg_handicap_over_manual(
        self, uow: InMemoryUnitOfWork, country_repository
    ):
        """
        Verifica que se prefiere el hándicap de RFEG sobre el manual
        cuando RFEG devuelve un valor.
        """
        # Arrange
        from src.modules.user.infrastructure.external.mock_handicap_service import (
            MockHandicapService,
        )

        # Servicio que devuelve un hándicap para este usuario
        handicap_service = MockHandicapService(handicaps={"Test User": 3.5})
        use_case = RegisterUserUseCase(uow, country_repository, handicap_service)

        request_dto = RegisterUserRequestDTO(
            email="test.user@example.com",
            password="V@l1dP@ss123!",
            first_name="Test",
            last_name="User",
            manual_handicap=20.0,  # Este será ignorado
        )

        # Act
        user_response = await use_case.execute(request_dto)

        # Assert - debe usar el de RFEG (3.5), no el manual (20.0)
        assert user_response.handicap == pytest.approx(3.5)

    async def test_should_register_without_handicap_when_none_available(
        self, uow: InMemoryUnitOfWork, country_repository
    ):
        """
        Verifica que se puede registrar un usuario sin hándicap
        cuando RFEG devuelve None y no se proporciona hándicap manual.
        """
        # Arrange
        from src.modules.user.infrastructure.external.mock_handicap_service import (
            MockHandicapService,
        )

        # Servicio que devuelve None
        handicap_service = MockHandicapService(default=None)
        use_case = RegisterUserUseCase(uow, country_repository, handicap_service)

        request_dto = RegisterUserRequestDTO(
            email="test.user@example.com",
            password="V@l1dP@ss123!",
            first_name="Test",
            last_name="User",
            # No manual_handicap
        )

        # Act
        user_response = await use_case.execute(request_dto)

        # Assert
        assert user_response.handicap is None
