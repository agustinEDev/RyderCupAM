from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.modules.user.application.dto.user_dto import FindUserRequestDTO, FindUserResponseDTO
from src.modules.user.application.use_cases.find_user_use_case import FindUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId

# Marcar todos los tests para ejecutarse con asyncio
pytestmark = pytest.mark.asyncio

class TestFindUserUseCase:
    """
    Suite de tests unitarios para FindUserUseCase.
    """

    @pytest.fixture
    def mock_uow(self):
        """Mock para Unit of Work."""
        uow = AsyncMock()
        uow.users = AsyncMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=None)
        return uow

    @pytest.fixture
    def sample_user(self):
        """Usuario de muestra para testing."""
        user = User(
            id=UserId(uuid4()),
            email=Email("test@example.com"),
            password=Password.from_plain_text("s3cur3P@ssw0rd!"),
            first_name="Test",
            last_name="User"
        )
        return user

    @pytest.fixture
    def use_case(self, mock_uow):
        """Instancia del caso de uso con mock dependencies."""
        return FindUserUseCase(mock_uow)

    async def test_find_user_by_email_successfully(self, use_case, mock_uow, sample_user):
        """
        Verifica que se puede encontrar un usuario por email correctamente.
        """
        # Arrange
        mock_uow.users.find_by_email.return_value = sample_user

        request = FindUserRequestDTO(
            email="test@example.com",
            full_name=None
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert isinstance(result, FindUserResponseDTO)
        assert result.user_id == sample_user.id.value
        assert result.email == sample_user.email.value
        assert result.full_name == "Test User"

        # Verificar que se llamó al método correcto
        mock_uow.users.find_by_email.assert_called_once()
        call_args = mock_uow.users.find_by_email.call_args[0][0]
        assert call_args.value == "test@example.com"

    async def test_find_user_by_full_name_successfully(self, use_case, mock_uow, sample_user):
        """
        Verifica que se puede encontrar un usuario por nombre completo.
        """
        # Arrange
        mock_uow.users.find_by_email.return_value = None  # No encontrado por email
        mock_uow.users.find_by_full_name.return_value = sample_user

        request = FindUserRequestDTO(
            email=None,
            full_name="Test User"
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert isinstance(result, FindUserResponseDTO)
        assert result.user_id == sample_user.id.value
        assert result.email == sample_user.email.value
        assert result.full_name == "Test User"

        # Verificar que se llamó al método correcto
        mock_uow.users.find_by_full_name.assert_called_once_with("Test User")

    async def test_find_user_prioritizes_email_over_name(self, use_case, mock_uow, sample_user):
        """
        Verifica que se prioriza la búsqueda por email cuando ambos parámetros están presentes.
        """
        # Arrange
        mock_uow.users.find_by_email.return_value = sample_user

        request = FindUserRequestDTO(
            email="test@example.com",
            full_name="Different User"
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result.email == sample_user.email.value

        # Verificar que se buscó por email pero NO por nombre
        mock_uow.users.find_by_email.assert_called_once()
        mock_uow.users.find_by_full_name.assert_not_called()

    async def test_find_user_falls_back_to_name_when_email_not_found(self, use_case, mock_uow, sample_user):
        """
        Verifica que se busca por nombre cuando no se encuentra por email.
        """
        # Arrange
        mock_uow.users.find_by_email.return_value = None  # No encontrado por email
        mock_uow.users.find_by_full_name.return_value = sample_user

        request = FindUserRequestDTO(
            email="notfound@example.com",
            full_name="Test User"
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result.full_name == "Test User"

        # Verificar que se intentó buscar por ambos métodos
        mock_uow.users.find_by_email.assert_called_once()
        mock_uow.users.find_by_full_name.assert_called_once_with("Test User")

    async def test_find_user_not_found_by_email_raises_error(self, use_case, mock_uow):
        """
        Verifica que se lanza UserNotFoundError cuando no se encuentra por email.
        """
        # Arrange
        mock_uow.users.find_by_email.return_value = None

        request = FindUserRequestDTO(
            email="notfound@example.com",
            full_name=None
        )

        # Act & Assert
        with pytest.raises(UserNotFoundError) as exc_info:
            await use_case.execute(request)

        assert "notfound@example.com" in str(exc_info.value)

    async def test_find_user_not_found_by_name_raises_error(self, use_case, mock_uow):
        """
        Verifica que se lanza UserNotFoundError cuando no se encuentra por nombre.
        """
        # Arrange
        mock_uow.users.find_by_full_name.return_value = None

        request = FindUserRequestDTO(
            email=None,
            full_name="Nonexistent User"
        )

        # Act & Assert
        with pytest.raises(UserNotFoundError) as exc_info:
            await use_case.execute(request)

        assert "Nonexistent User" in str(exc_info.value)

    async def test_find_user_not_found_by_either_criteria_raises_error(self, use_case, mock_uow):
        """
        Verifica que se lanza UserNotFoundError cuando no se encuentra por ningún criterio.
        """
        # Arrange
        mock_uow.users.find_by_email.return_value = None
        mock_uow.users.find_by_full_name.return_value = None

        request = FindUserRequestDTO(
            email="notfound@example.com",
            full_name="Nonexistent User"
        )

        # Act & Assert
        with pytest.raises(UserNotFoundError) as exc_info:
            await use_case.execute(request)

        error_message = str(exc_info.value)
        assert "notfound@example.com" in error_message
        assert "Nonexistent User" in error_message

    def test_find_user_validates_dto_constraints(self):
        """
        Verifica que el DTO valida correctamente las restricciones.
        """
        # Act & Assert - Sin ningún campo debe fallar
        with pytest.raises(ValueError) as exc_info:
            FindUserRequestDTO(email=None, full_name=None)

        assert "al menos" in str(exc_info.value).lower()

    def test_find_user_response_dto_structure(self, sample_user):
        """
        Verifica que el DTO de respuesta tiene la estructura correcta.
        """
        # Act
        response = FindUserResponseDTO(
            user_id=sample_user.id.value,
            email=sample_user.email.value,
            full_name=sample_user.get_full_name()
        )

        # Assert
        assert hasattr(response, 'user_id')
        assert hasattr(response, 'email')
        assert hasattr(response, 'full_name')
        assert response.user_id == sample_user.id.value
        assert response.email == sample_user.email.value
        assert response.full_name == "Test User"

    async def test_find_user_handles_complex_names(self, use_case, mock_uow):
        """
        Verifica que maneja correctamente nombres compuestos.
        """
        # Arrange
        complex_user = User(
            id=UserId(uuid4()),
            email=Email("complex@example.com"),
            password=Password.from_plain_text("s3cur3P@ssw0rd!"),
            first_name="María José",
            last_name="García-López de la Torre"
        )

        mock_uow.users.find_by_full_name.return_value = complex_user

        request = FindUserRequestDTO(
            email=None,
            full_name="María José García-López de la Torre"
        )

        # Act
        result = await use_case.execute(request)

        # Assert
        assert result.full_name == "María José García-López de la Torre"
        mock_uow.users.find_by_full_name.assert_called_once_with("María José García-López de la Torre")
