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

        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=None,  # Sin contexto HTTP
            ip_address=None,
        )

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

        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=None,  # Sin contexto HTTP
            ip_address=None,
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 2
        assert len(response.devices) == 2
        assert all(device.is_active for device in response.devices)
        # v1.13.1: Sin contexto HTTP, todos los dispositivos son is_current_device=False
        assert all(device.is_current_device is False for device in response.devices)

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

        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=None,  # Sin contexto HTTP
            ip_address=None,
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 1
        assert len(response.devices) == 1
        # Device name es auto-generado por DeviceFingerprint, no el pasado en el request
        assert response.devices[0].is_active is True
        # v1.13.1: Sin contexto HTTP, is_current_device=False
        assert response.devices[0].is_current_device is False

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

        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=None,  # Sin contexto HTTP
            ip_address=None,
        )

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
        # v1.13.1: Campo nuevo requerido
        assert device.is_current_device is False

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

        request = ListUserDevicesRequestDTO(
            user_id=str(user_id1.value),
            user_agent=None,  # Sin contexto HTTP
            ip_address=None,
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 1
        assert response.devices[0].device_name == "Chrome on macOS"
        # v1.13.1: Sin contexto HTTP, is_current_device=False
        assert response.devices[0].is_current_device is False

    # ===================================================================================
    # TESTS NUEVOS v1.13.1: is_current_device Detection
    # ===================================================================================

    async def test_is_current_device_true_when_fingerprint_matches(self, uow):
        """
        Test: is_current_device=True cuando el fingerprint coincide
        Given: Usuario con 1 dispositivo registrado
        When: Se lista con el MISMO user_agent + ip_address usado al registrarlo
        Then: El dispositivo tiene is_current_device=True
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Contexto HTTP específico
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"
        ip_address = "192.168.1.100"

        # Registrar dispositivo con estos valores
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )

        # Listar con el MISMO user_agent + ip_address
        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=user_agent,  # ← MISMO
            ip_address=ip_address,  # ← MISMO
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 1
        # ✅ El dispositivo debe estar marcado como actual
        assert response.devices[0].is_current_device is True

    async def test_is_current_device_false_when_fingerprint_differs(self, uow):
        """
        Test: is_current_device=False cuando el fingerprint NO coincide
        Given: Usuario con 1 dispositivo registrado (Chrome on macOS)
        When: Se lista con DIFERENTE user_agent + ip_address (Safari on iOS)
        Then: El dispositivo tiene is_current_device=False
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Registrar dispositivo 1 (Chrome on macOS)
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                ip_address="192.168.1.100",
            )
        )

        # Listar desde dispositivo 2 (Safari on iOS) - DIFERENTE
        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
            ip_address="192.168.1.101",  # ← IP diferente
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 1
        # ❌ El dispositivo NO debe estar marcado como actual (es otro dispositivo)
        assert response.devices[0].is_current_device is False

    async def test_is_current_device_all_false_without_context(self, uow):
        """
        Test: Todos is_current_device=False cuando NO hay contexto HTTP
        Given: Usuario con 3 dispositivos registrados
        When: Se lista SIN user_agent + ip_address (None)
        Then: TODOS los dispositivos tienen is_current_device=False
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Registrar 3 dispositivos diferentes
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                ip_address="192.168.1.100",
            )
        )
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
                ip_address="192.168.1.101",
            )
        )
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
                ip_address="192.168.1.102",
            )
        )

        # Listar SIN contexto HTTP
        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=None,  # ← SIN contexto
            ip_address=None,
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 3
        # ❌ TODOS deben ser False (no podemos determinar el actual sin contexto)
        assert all(device.is_current_device is False for device in response.devices)

    async def test_is_current_device_only_one_true_with_multiple_devices(self, uow):
        """
        Test: Solo UN dispositivo es is_current_device=True con múltiples dispositivos
        Given: Usuario con 4 dispositivos registrados
        When: Se lista con user_agent + ip_address del dispositivo 2
        Then: Solo dispositivo 2 tiene is_current_device=True, los demás False
        """
        # Arrange
        register_use_case = RegisterDeviceUseCase(uow)
        list_use_case = ListUserDevicesUseCase(uow)
        user_id = UserId.generate()

        # Contexto HTTP del dispositivo 2 (Safari on iOS)
        current_user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1"
        current_ip_address = "192.168.1.101"

        # Registrar 4 dispositivos diferentes
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                ip_address="192.168.1.100",
            )
        )
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent=current_user_agent,  # ← ESTE es el actual
                ip_address=current_ip_address,
            )
        )
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0",
                ip_address="192.168.1.102",
            )
        )
        await register_use_case.execute(
            RegisterDeviceRequestDTO(
                user_id=str(user_id.value),
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0",
                ip_address="192.168.1.103",
            )
        )

        # Listar desde el dispositivo 2
        request = ListUserDevicesRequestDTO(
            user_id=str(user_id.value),
            user_agent=current_user_agent,
            ip_address=current_ip_address,
        )

        # Act
        response = await list_use_case.execute(request)

        # Assert
        assert response.total_count == 4

        # Verificar que SOLO uno es True
        current_devices = [d for d in response.devices if d.is_current_device is True]
        assert len(current_devices) == 1

        # Verificar que los otros 3 son False
        other_devices = [d for d in response.devices if d.is_current_device is False]
        assert len(other_devices) == 3

        # El dispositivo actual debe ser "Safari on iOS"
        assert current_devices[0].device_name == "Safari on iOS"
