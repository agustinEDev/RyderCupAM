"""
Tests para ListUserDevicesUseCase

Tests unitarios para el caso de uso de listado de dispositivos de usuario.
"""

import pytest

from src.modules.user.application.dto.device_dto import (
    ListUserDevicesRequestDTO,
    RegisterDeviceRequestDTO,
)
from src.modules.user.application.use_cases.list_user_devices_use_case import (
    ListUserDevicesUseCase,
)
from src.modules.user.application.use_cases.register_device_use_case import (
    RegisterDeviceUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    """Fixture que proporciona un Unit of Work en memoria."""
    return InMemoryUnitOfWork()


@pytest.mark.asyncio
class TestListUserDevicesUseCase:
    """Tests para el caso de uso de listado de dispositivos."""

    async def test_list_devices_returns_empty_when_no_devices(self, uow):
        """
        Test: Listar dispositivos de usuario sin dispositivos
        Given: Usuario sin dispositivos registrados
        When: Se ejecuta ListUserDevicesUseCase
        Then: Retorna lista vacía y total_count=0
        """
        # Arrange
        use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        request = ListUserDevicesRequestDTO(user_id=str(user_id.value))

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        assert response.devices == []
        assert response.total_count == 0

    async def test_list_devices_returns_all_active_devices(self, uow):
        """
        Test: Listar dispositivos retorna todos los activos
        Given: Usuario con 2 dispositivos activos
        When: Se ejecuta ListUserDevicesUseCase
        Then: Retorna lista con 2 dispositivos y total_count=2
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Registrar 2 dispositivos
        await register_use_case.execute(
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

        request = ListUserDevicesRequestDTO(user_id=str(user_id.value))

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 2
        assert len(response.devices) == 2
        assert all(device.is_active for device in response.devices)

    async def test_list_devices_excludes_revoked_devices(self, uow):
        """
        Test: Listar dispositivos NO incluye dispositivos revocados
        Given: Usuario con 2 dispositivos (1 activo, 1 revocado)
        When: Se ejecuta ListUserDevicesUseCase
        Then: Retorna solo el dispositivo activo
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Registrar dispositivo 1 (activo)
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Chrome on macOS",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                ip_address="192.168.1.100",
            )
        )

        # Registrar dispositivo 2 y revocarlo
        response2 = await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Safari on iOS",
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                ip_address="192.168.1.101",
            )
        )

        # Revocar dispositivo 2 (acceso directo al repositorio para test)
        async with uow:
            from src.modules.user.domain.value_objects.user_device_id import (
                UserDeviceId,
            )

            device_id = UserDeviceId(response2.device_id)
            device = await uow.user_devices.find_by_id(device_id)
            device.revoke()
            await uow.user_devices.save(device)
            await uow.commit()

        request = ListUserDevicesRequestDTO(user_id=str(user_id.value))

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 1
        assert len(response.devices) == 1
        # Device name es auto-generado por DeviceFingerprint, no el pasado en el request
        assert response.devices[0].is_active is True

    async def test_list_devices_contains_all_required_fields(self, uow):
        """
        Test: Dispositivos listados contienen todos los campos
        Given: Usuario con 1 dispositivo
        When: Se ejecuta ListUserDevicesUseCase
        Then: DTO contiene todos los campos requeridos
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                device_name="Firefox on Windows",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
                ip_address="192.168.1.102",
            )
        )

        request = ListUserDevicesRequestDTO(user_id=str(user_id.value))

        # Act
        response = await list_use_case.execute(request)

        # Assert
        device = response.devices[0]
        assert device.id is not None
        assert device.device_name == "Firefox on Windows 10/11"
        assert device.ip_address == "192.168.1.102"
        assert device.last_used_at is not None
        assert device.created_at is not None
        assert device.is_active is True

    async def test_list_devices_for_different_users_isolated(self, uow):
        """
        Test: Dispositivos de usuarios diferentes están aislados
        Given: 2 usuarios con dispositivos propios
        When: Se listan dispositivos de user1
        Then: Solo se retornan dispositivos de user1
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id1 = UserId.generate()
        user_id2 = UserId.generate()

        # User 1: 1 dispositivo
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id1.value),
                device_name="Chrome on macOS",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                ip_address="192.168.1.100",
            )
        )

        # User 2: 2 dispositivos
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id2.value),
                device_name="Safari on iOS",
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                ip_address="192.168.1.101",
            )
        )
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id2.value),
                device_name="Firefox on Windows",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
                ip_address="192.168.1.102",
            )
        )

        request = ListUserDevicesRequestDTO(user_id=str(user_id1.value))

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 1
        assert response.devices[0].device_name == "Chrome on macOS"
