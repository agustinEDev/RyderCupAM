"""
Tests para RevokeDeviceUseCase

Tests unitarios para el caso de uso de revocación de dispositivos.
"""

import pytest

from src.modules.user.application.dto.device_dto import (
    RegisterDeviceRequestDTO,
    RevokeDeviceRequestDTO,
)
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.application.use_cases.revoke_device_use_case import (
    RevokeDeviceUseCase,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    """Fixture que proporciona un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.mark.asyncio
class TestRevokeDeviceUseCase:
    """Tests para el caso de uso de revocación de dispositivos."""

    async def test_revoke_device_marks_as_inactive(self, uow):
        """
        Test: Revocar dispositivo lo marca como inactivo
        Given: Dispositivo activo
        When: Se ejecuta RevokeDeviceUseCase
        Then: Dispositivo queda inactivo (is_active=False)
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        revoke_use_case = RevokeDeviceUseCase(uow)
        user_id = UserId.generate()

        # Registrar dispositivo
        register_response = await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Chrome on macOS",
                user_agent="Mozilla/5.0 (Macintosh)",
                ip_address="192.168.1.100",
            )
        )

        request = RevokeDeviceRequestDTO(
            user_id=str(user_id.value),
            device_id=register_response.device_id,
        )

        # Act
        response = await revoke_use_case.execute(request)

        # Assert
        assert response is not None
        assert response.message == "Dispositivo revocado exitosamente"
        assert response.device_id == register_response.device_id

        # Verificar que el dispositivo está inactivo
        async with uow:
            device_id = UserDeviceId.from_string(register_response.device_id)
            device = await uow.user_devices.find_by_id(device_id)
            assert device.is_active is False

    async def test_revoke_device_not_found_raises_error(self, uow):
        """
        Test: Revocar dispositivo inexistente lanza error
        Given: device_id que no existe en BD
        When: Se ejecuta RevokeDeviceUseCase
        Then: Lanza ValueError
        """
        # Arrange
        revoke_use_case = RevokeDeviceUseCase(uow)
        user_id = UserId.generate()
        non_existent_device_id = UserDeviceId.generate()

        request = RevokeDeviceRequestDTO(
            user_id=str(user_id.value),
            device_id=str(non_existent_device_id.value),
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await revoke_use_case.execute(request)

        assert "no encontrado" in str(exc_info.value)

    async def test_revoke_device_wrong_user_raises_permission_error(self, uow):
        """
        Test: Revocar dispositivo de otro usuario lanza PermissionError
        Given: Dispositivo de user1
        When: user2 intenta revocarlo
        Then: Lanza PermissionError
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        revoke_use_case = RevokeDeviceUseCase(uow)
        user_id1 = UserId.generate()
        user_id2 = UserId.generate()

        # User1 registra dispositivo
        register_response = await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id1.value),
                device_name="Chrome on macOS",
                user_agent="Mozilla/5.0 (Macintosh)",
                ip_address="192.168.1.100",
            )
        )

        # User2 intenta revocar dispositivo de User1
        request = RevokeDeviceRequestDTO(
            user_id=str(user_id2.value),  # Usuario diferente
            device_id=register_response.device_id,
        )

        # Act & Assert
        with pytest.raises(PermissionError) as exc_info:
            await revoke_use_case.execute(request)

        assert "No autorizado" in str(exc_info.value)

    async def test_revoke_already_revoked_device_raises_error(self, uow):
        """
        Test: Revocar dispositivo ya revocado lanza error
        Given: Dispositivo ya revocado
        When: Se intenta revocar nuevamente
        Then: Lanza RuntimeError
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        revoke_use_case = RevokeDeviceUseCase(uow)
        user_id = UserId.generate()

        # Registrar dispositivo
        register_response = await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Safari on iOS",
                user_agent="Mozilla/5.0 (iPhone)",
                ip_address="192.168.1.101",
            )
        )

        request = RevokeDeviceRequestDTO(
            user_id=str(user_id.value),
            device_id=register_response.device_id,
        )

        # Act - Primera revocación (exitosa)
        await revoke_use_case.execute(request)

        # Act & Assert - Segunda revocación (error)
        with pytest.raises(RuntimeError) as exc_info:
            await revoke_use_case.execute(request)

        assert "already revoked" in str(exc_info.value)

    async def test_revoke_device_with_invalid_device_id_raises_error(self, uow):
        """
        Test: device_id inválido lanza error
        Given: device_id que no es UUID válido
        When: Se ejecuta RevokeDeviceUseCase
        Then: Lanza ValueError
        """
        # Arrange
        revoke_use_case = RevokeDeviceUseCase(uow)
        user_id = UserId.generate()

        request = RevokeDeviceRequestDTO(
            user_id=str(user_id.value),
            device_id="invalid-device-id",
        )

        # Act & Assert
        with pytest.raises(ValueError):
            await revoke_use_case.execute(request)

    async def test_revoke_device_removes_from_active_list(self, uow):
        """
        Test: Dispositivo revocado NO aparece en listado de activos
        Given: 2 dispositivos activos
        When: Se revoca 1 dispositivo
        Then: Solo 1 aparece en listado activo
        """
        # Arrange
        from src.modules.user.application.dto.device_dto import ListUserDevicesRequestDTO
        from src.modules.user.application.use_cases.list_user_devices_use_case import (
            ListUserDevicesUseCase,
        )

        register_use_case = RegisterDeviceUseCase(uow)
        revoke_use_case = RevokeDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Registrar 2 dispositivos
        device1_response = await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Chrome on macOS",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                ip_address="192.168.1.100",
            )
        )

        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Safari on iOS",
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                ip_address="192.168.1.101",
            )
        )

        # Revocar dispositivo 1
        await revoke_use_case.execute(
            RevokeDeviceRequestDTO(
                user_id=str(user_id.value),
                device_id=device1_response.device_id,
            )
        )

        # Act - Listar dispositivos activos
        list_response = await list_use_case.execute(
            ListUserDevicesRequestDTO(user_id=str(user_id.value))
        )

        # Assert
        assert list_response.total_count == 1
        assert list_response.devices[0].device_name == "Safari on iOS"
