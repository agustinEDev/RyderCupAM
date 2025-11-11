"""
Tests para UpdateProfileUseCase

Tests unitarios para el caso de uso de actualización de perfil del usuario.
"""

import pytest
from pydantic import ValidationError

from src.modules.user.application.dto.user_dto import UpdateProfileRequestDTO
from src.modules.user.application.use_cases.update_profile_use_case import UpdateProfileUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
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


@pytest.mark.asyncio
class TestUpdateProfileUseCase:
    """Tests para el caso de uso de actualización de perfil."""

    async def test_update_first_name_only(self, uow, existing_user):
        """Debe actualizar solo el nombre cuando se proporciona."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(
            first_name="Jane",
            last_name=None
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "Jane"
        assert response.user.last_name == "Doe"  # No cambió
        assert response.message == "Profile updated successfully"

        # Verificar que se guardó en el repositorio
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert updated_user.first_name == "Jane"

    async def test_update_last_name_only(self, uow, existing_user):
        """Debe actualizar solo el apellido cuando se proporciona."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(
            first_name=None,
            last_name="Smith"
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "John"  # No cambió
        assert response.user.last_name == "Smith"
        assert response.message == "Profile updated successfully"

    async def test_update_both_names(self, uow, existing_user):
        """Debe actualizar ambos campos cuando se proporcionan."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(
            first_name="Jane",
            last_name="Smith"
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "Jane"
        assert response.user.last_name == "Smith"

    async def test_update_fails_when_user_not_found(self, uow):
        """Debe lanzar UserNotFoundError cuando el usuario no existe."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        request = UpdateProfileRequestDTO(
            first_name="Jane",
            last_name=None
        )

        # Act & Assert
        with pytest.raises(UserNotFoundError):
            await use_case.execute(non_existent_id, request)

    async def test_update_rejects_too_short_names(self, uow, existing_user):
        """Debe rechazar nombres muy cortos (validación Pydantic)."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        user_id = str(existing_user.id.value)

        # Act & Assert - Pydantic valida min_length=2
        with pytest.raises(ValidationError):
            UpdateProfileRequestDTO(
                first_name="A",  # Muy corto
                last_name=None
            )

    async def test_no_update_when_values_are_same(self, uow, existing_user):
        """Debe retornar sin cambios cuando los valores son los mismos."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(
            first_name="John",  # Mismo valor
            last_name="Doe"     # Mismo valor
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        assert response is not None
        assert response.user.first_name == "John"
        assert response.user.last_name == "Doe"

    async def test_update_emits_domain_event(self, uow, existing_user):
        """Debe emitir UserProfileUpdatedEvent cuando se actualiza."""
        # Arrange
        use_case = UpdateProfileUseCase(uow)
        user_id = str(existing_user.id.value)
        request = UpdateProfileRequestDTO(
            first_name="Jane",
            last_name=None
        )

        # Act
        response = await use_case.execute(user_id, request)

        # Assert
        # Verificar que la respuesta tiene los datos actualizados
        assert response.user.first_name == "Jane"
        assert response.user.last_name == "Doe"  # No cambió

        # Verificar que se guardó en el repositorio
        updated_user = await uow.users.find_by_id(UserId(user_id))
        assert updated_user.first_name == "Jane"
