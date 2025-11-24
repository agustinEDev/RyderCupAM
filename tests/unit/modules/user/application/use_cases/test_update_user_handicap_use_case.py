"""
Tests for UpdateUserHandicapUseCase
"""

import pytest
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.application.use_cases.update_user_handicap_use_case import UpdateUserHandicapUseCase
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import InMemoryUnitOfWork
from src.modules.user.infrastructure.external.mock_handicap_service import MockHandicapService


class TestUpdateUserHandicapUseCase:
    """Tests para el caso de uso UpdateUserHandicapUseCase."""

    @pytest.mark.asyncio
    async def test_update_handicap_for_existing_user(self):
        """Test: Actualizar hándicap de un usuario existente."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Rafael", "Nadal Parera", "rafa@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        handicap_service = MockHandicapService(
            handicaps={"Rafael Nadal Parera": 2.5}
        )
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        # Act
        result = await use_case.execute(user.id)

        # Assert
        assert result is not None
        assert result.handicap == pytest.approx(2.5)

    @pytest.mark.asyncio
    async def test_update_handicap_for_non_existent_user(self):
        """Test: Actualizar hándicap de usuario que no existe devuelve None."""
        # Arrange
        uow = InMemoryUnitOfWork()
        handicap_service = MockHandicapService(default=15.0)
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        non_existent_id = UserId.generate()

        # Act
        result = await use_case.execute(non_existent_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_update_handicap_when_service_returns_none(self):
        """Test: Lanza HandicapNotFoundError cuando el servicio devuelve None y no hay manual_handicap."""
        from src.modules.user.domain.errors.handicap_errors import HandicapNotFoundError

        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Unknown", "Player", "unknown@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        handicap_service = MockHandicapService(default=None)
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        # Act & Assert
        with pytest.raises(HandicapNotFoundError, match="No se encontró hándicap en RFEG"):
            await use_case.execute(user.id)

    @pytest.mark.asyncio
    async def test_update_handicap_persists_change(self):
        """Test: El cambio de hándicap se persiste correctamente."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Carlos", "Alcaraz Garfia", "carlos@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        handicap_service = MockHandicapService(
            handicaps={"Carlos Alcaraz Garfia": 5.0}
        )
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        # Act
        await use_case.execute(user.id)

        # Assert - verificar que se guardó en el repositorio
        saved_user = await uow.users.find_by_id(user.id)
        assert saved_user.handicap.value == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_update_handicap_uses_manual_when_rfeg_returns_none(self):
        """Test: Usa hándicap manual cuando RFEG devuelve None."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        # Servicio que devuelve None (jugador no encontrado)
        handicap_service = MockHandicapService(default=None)
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        # Act - proporcionar hándicap manual
        result = await use_case.execute(user.id, manual_handicap=18.5)

        # Assert
        assert result is not None
        assert result.handicap == pytest.approx(18.5)

    @pytest.mark.asyncio
    async def test_update_handicap_prefers_rfeg_over_manual(self):
        """Test: Prefiere RFEG sobre hándicap manual si RFEG devuelve valor."""
        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Rafael", "Nadal Parera", "rafa@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        # Servicio que devuelve un valor
        handicap_service = MockHandicapService(
            handicaps={"Rafael Nadal Parera": 2.5}
        )
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        # Act - proporcionar hándicap manual pero RFEG tiene valor
        result = await use_case.execute(user.id, manual_handicap=20.0)

        # Assert - debe usar el de RFEG (2.5), no el manual (20.0)
        assert result is not None
        assert result.handicap == pytest.approx(2.5)

    @pytest.mark.asyncio
    async def test_update_handicap_no_change_when_both_none(self):
        """Test: Lanza HandicapNotFoundError cuando RFEG devuelve None y no hay hándicap manual."""
        from src.modules.user.domain.errors.handicap_errors import HandicapNotFoundError

        # Arrange
        uow = InMemoryUnitOfWork()
        user = User.create("Test", "User", "test@test.com", "Pass123!")
        await uow.users.save(user)
        await uow.commit()

        # Servicio que devuelve None
        handicap_service = MockHandicapService(default=None)
        use_case = UpdateUserHandicapUseCase(uow, handicap_service)

        # Act & Assert - debe lanzar error porque no hay hándicap en RFEG ni manual
        with pytest.raises(HandicapNotFoundError, match="No se encontró hándicap en RFEG"):
            await use_case.execute(user.id, manual_handicap=None)


class TestUpdateMultipleHandicapsUseCase:
    """Tests para el caso de uso UpdateMultipleHandicapsUseCase."""

    @pytest.mark.asyncio
    async def test_update_multiple_users_successfully(self):
        """Test: Actualizar hándicaps de múltiples usuarios exitosamente."""
        from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import UpdateMultipleHandicapsUseCase

        # Arrange
        uow = InMemoryUnitOfWork()
        user1 = User.create("Rafael", "Nadal Parera", "rafa@test.com", "Pass123!")
        user2 = User.create("Carlos", "Alcaraz Garfia", "carlos@test.com", "Pass123!")
        await uow.users.save(user1)
        await uow.users.save(user2)
        await uow.commit()

        handicap_service = MockHandicapService(
            handicaps={
                "Rafael Nadal Parera": 2.5,
                "Carlos Alcaraz Garfia": 5.0
            }
        )
        use_case = UpdateMultipleHandicapsUseCase(uow, handicap_service)

        # Act
        stats = await use_case.execute([user1.id, user2.id])

        # Assert
        assert stats['total'] == 2
        assert stats['updated'] == 2
        assert stats['not_found'] == 0
        assert stats['no_handicap_found'] == 0
        assert stats['errors'] == 0

    @pytest.mark.asyncio
    async def test_update_multiple_with_non_existent_users(self):
        """Test: Estadísticas correctas cuando algunos usuarios no existen."""
        from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import UpdateMultipleHandicapsUseCase

        # Arrange
        uow = InMemoryUnitOfWork()
        user1 = User.create("Rafael", "Nadal Parera", "rafa@test.com", "Pass123!")
        await uow.users.save(user1)
        await uow.commit()

        handicap_service = MockHandicapService(default=15.0)
        use_case = UpdateMultipleHandicapsUseCase(uow, handicap_service)

        non_existent_id = UserId.generate()

        # Act
        stats = await use_case.execute([user1.id, non_existent_id])

        # Assert
        assert stats['total'] == 2
        assert stats['updated'] == 1
        assert stats['not_found'] == 1
        assert stats['no_handicap_found'] == 0
        assert stats['errors'] == 0

    @pytest.mark.asyncio
    async def test_update_multiple_empty_list(self):
        """Test: Actualizar lista vacía devuelve estadísticas correctas."""
        from src.modules.user.application.use_cases.update_multiple_handicaps_use_case import UpdateMultipleHandicapsUseCase

        # Arrange
        uow = InMemoryUnitOfWork()
        handicap_service = MockHandicapService(default=15.0)
        use_case = UpdateMultipleHandicapsUseCase(uow, handicap_service)

        # Act
        stats = await use_case.execute([])

        # Assert
        assert stats['total'] == 0
        assert stats['updated'] == 0
        assert stats['not_found'] == 0
        assert stats['no_handicap_found'] == 0
        assert stats['errors'] == 0
