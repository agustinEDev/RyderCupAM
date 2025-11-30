"""
Tests for UpdateUserHandicapManuallyUseCase
"""

import pytest

from src.modules.user.application.use_cases.update_user_handicap_manually_use_case import (
    UpdateUserHandicapManuallyUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


class TestUpdateUserHandicapManuallyUseCase:
    """Tests para el caso de uso UpdateUserHandicapManuallyUseCase."""

    @pytest.mark.asyncio
    async def test_update_handicap_manually_for_existing_user(self):
        """Test: Actualizar hándicap manualmente de un usuario existente."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        use_case = UpdateUserHandicapManuallyUseCase(uow)

        # Act
        result = await use_case.execute(user.id, 12.5)

        # Assert
        assert result is not None
        assert result.handicap == pytest.approx(12.5)

    @pytest.mark.asyncio
    async def test_update_handicap_manually_for_non_existent_user(self):
        """Test: Actualizar hándicap de usuario que no existe devuelve None."""
        # Arrange
        uow = InMemoryUnitOfWork()
        use_case = UpdateUserHandicapManuallyUseCase(uow)

        non_existent_id = UserId.generate()

        # Act
        result = await use_case.execute(non_existent_id, 15.0)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_update_handicap_manually_validates_range(self):
        """Test: Valida que el hándicap esté en el rango correcto."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        use_case = UpdateUserHandicapManuallyUseCase(uow)

        # Act & Assert - valor fuera de rango
        with pytest.raises(ValueError, match=r"entre -10\.0 y 54\.0"):
            await use_case.execute(user.id, 100.0)

    @pytest.mark.asyncio
    async def test_update_handicap_manually_persists_change(self):
        """Test: El cambio de hándicap se persiste correctamente."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        use_case = UpdateUserHandicapManuallyUseCase(uow)

        # Act
        await use_case.execute(user.id, 8.5)

        # Assert - verificar que se guardó en el repositorio
        saved_user = await uow.users.find_by_id(user.id)
        assert saved_user.handicap.value == pytest.approx(8.5)

    @pytest.mark.asyncio
    async def test_update_handicap_manually_changes_updated_at(self):
        """Test: Actualizar hándicap cambia el timestamp updated_at."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        original_updated_at = user.updated_at
        use_case = UpdateUserHandicapManuallyUseCase(uow)

        # Act
        import asyncio
        await asyncio.sleep(0.01)  # Pequeña pausa para asegurar cambio de timestamp
        result = await use_case.execute(user.id, 10.0)

        # Assert
        assert result.updated_at > original_updated_at

    @pytest.mark.asyncio
    async def test_update_handicap_manually_with_negative_value(self):
        """Test: Puede actualizar con valores negativos válidos."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        use_case = UpdateUserHandicapManuallyUseCase(uow)

        # Act
        result = await use_case.execute(user.id, -5.0)

        # Assert
        assert result is not None
        assert result.handicap == pytest.approx(-5.0)
