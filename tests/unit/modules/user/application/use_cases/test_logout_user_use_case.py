"""
Tests para LogoutUserUseCase

Tests unitarios para el caso de uso de logout de usuario.
"""

from datetime import datetime

import pytest

from src.modules.user.application.dto.user_dto import (
    LogoutRequestDTO,
    LogoutResponseDTO,
)
from src.modules.user.application.use_cases.logout_user_use_case import (
    LogoutUserUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    """Fixture que proporciona un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.fixture
async def existing_user(uow):
    """
    Fixture que crea un usuario existente en el sistema.
    Email: test@example.com
    Password: ValidPass123
    """
    user = User.create(
        first_name="Test",
        last_name="User",
        email_str="test@example.com",
        plain_password="V@l1dP@ss123!",
    )

    async with uow:
        await uow.users.save(user)
        await uow.commit()

    return user


@pytest.fixture
def use_case(uow):
    """Fixture que proporciona el caso de uso de logout."""
    return LogoutUserUseCase(uow)


class TestLogoutUserUseCase:
    """Tests para el caso de uso LogoutUserUseCase."""

    async def test_logout_successful_with_existing_user(self, use_case, existing_user):
        """
        Test: Logout exitoso con usuario existente
        Given: Un usuario existente en el sistema
        When: Se ejecuta logout con su user_id
        Then: Retorna confirmación de logout exitoso
        """
        # Arrange
        request = LogoutRequestDTO()
        user_id = str(existing_user.id.value)
        token = "sample-jwt-token"

        # Act
        result = await use_case.execute(request, user_id, token)

        # Assert
        assert result is not None
        assert isinstance(result, LogoutResponseDTO)
        assert result.message == "Logout exitoso"
        assert isinstance(result.logged_out_at, datetime)

    async def test_logout_with_nonexistent_user(self, use_case):
        """
        Test: Logout con usuario inexistente
        Given: Un user_id que no existe en el sistema
        When: Se ejecuta logout
        Then: Retorna None (usuario no encontrado)
        """
        # Arrange
        request = LogoutRequestDTO()
        non_existent_user_id = (
            "12345678-1234-5678-1234-567812345678"  # UUID válido pero inexistente
        )
        token = "sample-jwt-token"

        # Act
        result = await use_case.execute(request, non_existent_user_id, token)

        # Assert
        assert result is None

    async def test_logout_without_token(self, use_case, existing_user):
        """
        Test: Logout sin token (token opcional)
        Given: Un usuario existente
        When: Se ejecuta logout sin proporcionar token
        Then: Retorna confirmación exitosa (token es opcional en Fase 1)
        """
        # Arrange
        request = LogoutRequestDTO()
        user_id = str(existing_user.id.value)

        # Act
        result = await use_case.execute(request, user_id, token=None)

        # Assert
        assert result is not None
        assert isinstance(result, LogoutResponseDTO)
        assert result.message == "Logout exitoso"

    async def test_logout_response_structure(self, use_case, existing_user):
        """
        Test: Estructura correcta de la respuesta de logout
        Given: Un logout exitoso
        When: Se examina la respuesta
        Then: Contiene todos los campos esperados con tipos correctos
        """
        # Arrange
        request = LogoutRequestDTO()
        user_id = str(existing_user.id.value)
        token = "test-jwt-token"

        # Act
        result = await use_case.execute(request, user_id, token)

        # Assert
        assert result is not None
        assert hasattr(result, "message")
        assert hasattr(result, "logged_out_at")
        assert isinstance(result.message, str)
        assert isinstance(result.logged_out_at, datetime)

    async def test_logout_timestamp_is_recent(self, use_case, existing_user):
        """
        Test: El timestamp de logout es reciente
        Given: Un logout exitoso
        When: Se verifica el timestamp
        Then: Es muy cercano al momento actual
        """
        # Arrange
        request = LogoutRequestDTO()
        user_id = str(existing_user.id.value)
        token = "test-jwt-token"
        before_logout = datetime.now()

        # Act
        result = await use_case.execute(request, user_id, token)

        # Assert
        after_logout = datetime.now()
        assert result is not None
        assert before_logout <= result.logged_out_at <= after_logout
