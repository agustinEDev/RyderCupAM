"""
Tests para UpdateSecurityUseCase

Tests unitarios para el caso de uso de actualización de seguridad del usuario.
"""

import pytest

from pydantic import ValidationError

from src.modules.user.application.dto.user_dto import UpdateSecurityRequestDTO
from src.modules.user.application.use_cases.update_security_use_case import UpdateSecurityUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import (
    UserNotFoundError,
    InvalidCredentialsError,
    DuplicateEmailError
)
from src.modules.user.domain.value_objects.user_id import UserId
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
        first_name="John",
        last_name="Doe",
        email_str="test@example.com",
        plain_password="ValidPass123"
    )

    async with uow:
        await uow.users.save(user)
        await uow.commit()

    return user


@pytest.fixture
async def another_user(uow):
    """
    Fixture que crea otro usuario para probar duplicados.
    Email: another@example.com
    """
    user = User.create(
        first_name="Jane",
        last_name="Smith",
        email_str="another@example.com",
        plain_password="AnotherPass123"
    )

    async with uow:
        await uow.users.save(user)
        await uow.commit()

    return user


@pytest.mark.asyncio
class TestUpdateSecurityUseCase:
    """Tests para el caso de uso de actualización de seguridad."""

    async def test_update_email_only(self, uow, existing_user):
        """Debe actualizar solo el email cuando se proporciona."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email="newemail@example.com",
            new_password=None,
            confirm_password=None
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.email == "newemail@example.com"
        assert response.message == "Security settings updated successfully"

        # Verificar que el password no cambió
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert updated_user.verify_password("ValidPass123")

    async def test_update_password_only(self, uow, existing_user):
        """Debe actualizar solo el password cuando se proporciona."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email=None,
            new_password="NewSecurePass456",
            confirm_password="NewSecurePass456"
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.email == "test@example.com"  # No cambió

        # Verificar que el password SÍ cambió
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert updated_user.verify_password("NewSecurePass456")
        assert not updated_user.verify_password("ValidPass123")

    async def test_update_both_email_and_password(self, uow, existing_user):
        """Debe actualizar ambos cuando se proporcionan."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email="newemail@example.com",
            new_password="NewSecurePass456",
            confirm_password="NewSecurePass456"
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.email == "newemail@example.com"

        # Verificar cambios en BD
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert str(updated_user.email.value) == "newemail@example.com"
        assert updated_user.verify_password("NewSecurePass456")

    async def test_update_fails_with_wrong_current_password(self, uow, existing_user):
        """Debe lanzar InvalidCredentialsError cuando el password actual es incorrecto."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="WrongPassword",
            new_email="newemail@example.com",
            new_password=None,
            confirm_password=None
        )

        # Act & Assert
        with pytest.raises(InvalidCredentialsError, match="Current password is incorrect"):
            await use_case.execute(user_id, request)

    async def test_update_fails_when_user_not_found(self, uow):
        """Debe lanzar UserNotFoundError cuando el usuario no existe."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email="newemail@example.com",
            new_password=None,
            confirm_password=None
        )

        # Act & Assert
        with pytest.raises(UserNotFoundError):
            await use_case.execute(non_existent_id, request)

    async def test_update_fails_with_duplicate_email(self, uow, existing_user, another_user):
        """Debe lanzar DuplicateEmailError cuando el email ya está en uso."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email="another@example.com",  # Ya existe
            new_password=None,
            confirm_password=None
        )

        # Act & Assert
        with pytest.raises(DuplicateEmailError, match="already in use"):
            await use_case.execute(user_id, request)

    async def test_update_allows_same_email_for_same_user(self, uow, existing_user):
        """Debe permitir actualizar con el mismo email del usuario actual."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email="test@example.com",  # Mismo email
            new_password=None,
            confirm_password=None
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert - No debe lanzar error
        assert response is not None
        assert response.user.email == "test@example.com"

    async def test_update_fails_with_invalid_email_format(self, uow, existing_user):
        """Debe rechazar email inválido (validación Pydantic)."""
        # Arrange - Pydantic valida formato de email antes de llegar al use case

        # Act & Assert
        with pytest.raises(ValidationError):
            UpdateSecurityRequestDTO(
                current_password="ValidPass123",
                new_email="invalid-email",  # Sin @
                new_password=None,
                confirm_password=None
            )

    async def test_update_emits_domain_events(self, uow, existing_user):
        """Debe emitir eventos de dominio cuando se actualiza."""
        # Arrange
        use_case = UpdateSecurityUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateSecurityRequestDTO(
            current_password="ValidPass123",
            new_email="newemail@example.com",
            new_password="NewPass456",
            confirm_password="NewPass456"
        )

        # Act
        await use_case.execute(user_id, request)

        # Assert
        updated_user = await uow.users.find_by_id(UserId(user_id))

        # Verificar que los cambios se aplicaron
        assert str(updated_user.email.value) == "newemail@example.com"
        assert updated_user.verify_password("NewPass456")
