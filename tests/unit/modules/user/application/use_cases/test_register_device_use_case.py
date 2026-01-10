"""
Tests para RegisterDeviceUseCase

Tests unitarios para el caso de uso de registro/actualización de dispositivos.
"""

import pytest

from src.modules.user.application.dto.device_dto import RegisterDeviceRequestDTO
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
class TestRegisterDeviceUseCase:
    """Tests para el caso de uso de registro de dispositivos."""

    async def test_register_new_device_creates_device(self, uow):
        """
        Test: Registrar dispositivo nuevo lo crea en BD
        Given: user_id y datos de dispositivo nuevo
        When: Se ejecuta RegisterDeviceUseCase
        Then: Se crea dispositivo y retorna is_new_device=True
        """
        # Arrange
        use_case = RegisterDeviceUseCase(uow)
        user_id = UserId.generate()

        request = RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            device_name="Chrome 120.0 on macOS",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
            ip_address="192.168.1.100",
        )

        # Act
        response = await use_case.execute(request)

        # Assert
        assert response is not None
        assert response.is_new_device is True
        assert response.device_id is not None
        assert "Nuevo dispositivo detectado" in response.message
        # Device name es auto-generado por DeviceFingerprint.create()
        assert "Chrome on macOS" in response.message

    async def test_register_existing_device_updates_last_used(self, uow):
        """
        Test: Registrar dispositivo existente actualiza last_used_at
        Given: Dispositivo ya registrado
        When: Se registra nuevamente con mismo fingerprint
        Then: Se actualiza last_used_at y retorna is_new_device=False
        """
        # Arrange
        use_case = RegisterDeviceUseCase(uow)
        user_id = UserId.generate()

        request = RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            device_name="Safari 17.0 on iOS",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
            ip_address="192.168.1.101",
        )

        # Act - Primera vez (crear)
        response1 = await use_case.execute(request)

        # Act - Segunda vez (actualizar)
        response2 = await use_case.execute(request)

        # Assert
        assert response1.is_new_device is True
        assert response2.is_new_device is False
        assert response1.device_id == response2.device_id
        assert "Dispositivo conocido actualizado" in response2.message

    async def test_register_device_with_different_fingerprint_creates_new(self, uow):
        """
        Test: Dispositivo con fingerprint diferente crea nuevo registro
        Given: user_id con dispositivo existente
        When: Se registra dispositivo con diferente user_agent o IP
        Then: Se crea nuevo dispositivo (diferente fingerprint hash)
        """
        # Arrange
        use_case = RegisterDeviceUseCase(uow)
        user_id = UserId.generate()

        request1 = RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            device_name="Chrome on macOS",
            user_agent="Mozilla/5.0 (Macintosh)",
            ip_address="192.168.1.100",
        )

        request2 = RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            device_name="Chrome on Windows",
            user_agent="Mozilla/5.0 (Windows)",  # Diferente user_agent
            ip_address="192.168.1.100",
        )

        # Act
        response1 = await use_case.execute(request1)
        response2 = await use_case.execute(request2)

        # Assert
        assert response1.is_new_device is True
        assert response2.is_new_device is True
        assert response1.device_id != response2.device_id

    async def test_register_device_different_ip_creates_new(self, uow):
        """
        Test: Mismo dispositivo con IP diferente crea nuevo registro
        Given: Mismo user_agent pero IP diferente
        When: Se registra dispositivo
        Then: Se crea nuevo (fingerprint considera IP)
        """
        # Arrange
        use_case = RegisterDeviceUseCase(uow)
        user_id = UserId.generate()

        request1 = RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            device_name="Firefox on Windows",
            user_agent="Mozilla/5.0 (Windows NT 10.0)",
            ip_address="192.168.1.100",
        )

        request2 = RegisterDeviceRequestDTO(
            user_id=str(user_id.value),
            device_name="Firefox on Windows",
            user_agent="Mozilla/5.0 (Windows NT 10.0)",
            ip_address="192.168.1.200",  # IP diferente
        )

        # Act
        response1 = await use_case.execute(request1)
        response2 = await use_case.execute(request2)

        # Assert
        assert response1.is_new_device is True
        assert response2.is_new_device is True
        assert response1.device_id != response2.device_id

    async def test_register_device_for_different_users(self, uow):
        """
        Test: Mismo fingerprint para usuarios diferentes crea dispositivos separados
        Given: Dos usuarios con mismo dispositivo (mismo fingerprint)
        When: Se registran dispositivos
        Then: Se crean 2 dispositivos separados
        """
        # Arrange
        use_case = RegisterDeviceUseCase(uow)
        user_id1 = UserId.generate()
        user_id2 = UserId.generate()

        request1 = RegisterDeviceRequestDTO(
            user_id=str(user_id1.value),
            device_name="Chrome on macOS",
            user_agent="Mozilla/5.0 (Macintosh)",
            ip_address="192.168.1.100",
        )

        request2 = RegisterDeviceRequestDTO(
            user_id=str(user_id2.value),
            device_name="Chrome on macOS",
            user_agent="Mozilla/5.0 (Macintosh)",
            ip_address="192.168.1.100",
        )

        # Act
        response1 = await use_case.execute(request1)
        response2 = await use_case.execute(request2)

        # Assert
        assert response1.is_new_device is True
        assert response2.is_new_device is True
        assert response1.device_id != response2.device_id

    async def test_register_device_with_invalid_user_id_raises_error(self, uow):
        """
        Test: user_id inválido lanza error
        Given: user_id que no es UUID válido
        When: Se ejecuta RegisterDeviceUseCase
        Then: Lanza InvalidUserIdError
        """
        # Arrange
        from src.modules.user.domain.value_objects.user_id import InvalidUserIdError

        use_case = RegisterDeviceUseCase(uow)

        request = RegisterDeviceRequestDTO(
            user_id="invalid-uuid",
            device_name="Chrome",
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1",
        )

        # Act & Assert
        with pytest.raises(InvalidUserIdError):
            await use_case.execute(request)
