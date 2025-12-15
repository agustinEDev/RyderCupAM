"""
Tests para LoginUserUseCase

Tests unitarios para el caso de uso de login de usuario.
"""

import pytest

from src.modules.user.application.dto.user_dto import LoginRequestDTO
from src.modules.user.application.use_cases.login_user_use_case import LoginUserUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.shared.infrastructure.security.jwt_handler import JWTTokenService


@pytest.fixture
def uow():
    """Fixture que proporciona un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.fixture
def token_service():
    """Fixture que proporciona el servicio de tokens JWT."""
    return JWTTokenService()


@pytest.fixture
async def existing_user(uow):
    """
    Fixture que crea un usuario existente en el sistema.
    Email: test@example.com
    Password: ValidPass123
    """
    user = User.create(
        first_name="John",
        last_name="Doe",
        email_str="test@example.com",
        plain_password="V@l1dP@ss123!"
    )

    async with uow:
        await uow.users.save(user)
        await uow.commit()

    return user


@pytest.mark.asyncio
class TestLoginUserUseCase:
    """Tests para el caso de uso de login."""

    async def test_login_successful_with_correct_credentials(self, uow, token_service, existing_user):
        """Debe retornar token JWT cuando las credenciales son correctas."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service)
        request = LoginRequestDTO(
            email="test@example.com",
            password="V@l1dP@ss123!"
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        assert response.access_token is not None
        assert len(response.access_token) > 0
        assert response.token_type == "bearer"
        assert response.user.email == "test@example.com"
        assert response.user.first_name == "John"
        assert response.user.last_name == "Doe"
        assert response.user.id == existing_user.id.value

    async def test_login_fails_with_wrong_password(self, uow, token_service, existing_user):
        """Debe retornar None cuando la contraseña es incorrecta."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service)
        request = LoginRequestDTO(
            email="test@example.com",
            password="Wr0ngP@ssw0rd!"
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

    async def test_login_fails_with_non_existent_email(self, uow, token_service):
        """Debe retornar None cuando el email no existe."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service)
        request = LoginRequestDTO(
            email="nonexistent@example.com",
            password="S0m3P@ssw0rd!"
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is None

    async def test_login_response_does_not_include_password(self, uow, token_service, existing_user):
        """Debe asegurarse que la respuesta NO incluye la contraseña."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service)
        request = LoginRequestDTO(
            email="test@example.com",
            password="V@l1dP@ss123!"
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        response_dict = response.model_dump()
        assert "password" not in response_dict["user"]

    async def test_login_token_contains_user_id_in_subject(self, uow, token_service, existing_user):
        """Debe incluir el user_id en el subject del token."""
        # Arrange
        use_case = LoginUserUseCase(uow, token_service)
        request = LoginRequestDTO(
            email="test@example.com",
            password="V@l1dP@ss123!"
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None

        # Verificar que el token se puede decodificar
        from src.shared.infrastructure.security.jwt_handler import verify_access_token
        payload = verify_access_token(response.access_token)

        assert payload is not None
        assert "sub" in payload
        assert payload["sub"] == str(existing_user.id.value)
        assert "exp" in payload  # Debe tener tiempo de expiración
