"""
Tests unitarios para la Entity UserDevice.

Este archivo contiene tests que verifican:
- Creación de dispositivos con create()
- Actualización de last_used_at
- Revocación de dispositivos
- Reconstrucción desde BD (reconstitute)
- Validación de invariantes
- Eventos de dominio
"""

from datetime import datetime

import pytest

from src.modules.user.domain.entities.user_device import UserDevice
from src.modules.user.domain.events.device_revoked_event import DeviceRevokedEvent
from src.modules.user.domain.events.new_device_detected_event import (
    NewDeviceDetectedEvent,
)
from src.modules.user.domain.value_objects.device_fingerprint import DeviceFingerprint
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class TestUserDeviceCreation:
    """Tests para la creación de UserDevice"""

    def test_create_with_valid_data(self):
        """
        Test: create() crea dispositivo nuevo
        Given: user_id y fingerprint válidos
        When: Se crea UserDevice
        Then: Se crea correctamente con valores iniciales
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "192.168.1.100"
        )

        # Act
        device = UserDevice.create(user_id, fingerprint)

        # Assert
        assert device.id is not None
        assert isinstance(device.id, UserDeviceId)
        assert device.user_id == user_id
        assert device.device_name == fingerprint.device_name
        assert device.user_agent == fingerprint.user_agent
        assert device.ip_address == fingerprint.ip_address
        assert device.fingerprint_hash == fingerprint.fingerprint_hash
        assert device.is_active is True
        assert isinstance(device.created_at, datetime)
        assert isinstance(device.last_used_at, datetime)

    def test_create_generates_unique_id(self):
        """
        Test: create() genera IDs únicos
        Given: Múltiples creaciones con mismo fingerprint
        When: Se crean varios UserDevice
        Then: Cada uno tiene ID único
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0 (iPhone)", "192.168.1.101")

        # Act
        device1 = UserDevice.create(user_id, fingerprint)
        device2 = UserDevice.create(user_id, fingerprint)

        # Assert
        assert device1.id != device2.id

    def test_create_sets_timestamps_correctly(self):
        """
        Test: create() establece created_at y last_used_at
        Given: Creación de dispositivo
        When: Se crea UserDevice
        Then: created_at y last_used_at son iguales (ambos en creación)
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0 (Windows NT 10.0)", "192.168.1.102")

        # Act
        device = UserDevice.create(user_id, fingerprint)

        # Assert
        assert device.created_at == device.last_used_at

    def test_create_emits_new_device_detected_event(self):
        """
        Test: create() emite NewDeviceDetectedEvent
        Given: Creación de dispositivo nuevo
        When: Se crea UserDevice
        Then: Se emite evento NewDeviceDetectedEvent
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.100")

        # Act
        device = UserDevice.create(user_id, fingerprint)

        # Assert
        assert len(device.domain_events()) == 1
        event = device.domain_events()[0]
        assert isinstance(event, NewDeviceDetectedEvent)
        assert event.user_id == user_id
        assert event.device_name == fingerprint.device_name
        assert event.ip_address == fingerprint.ip_address
        assert event.user_agent == fingerprint.user_agent


class TestUserDeviceUpdateLastUsed:
    """Tests para update_last_used()"""

    def test_update_last_used_changes_timestamp(self):
        """
        Test: update_last_used() actualiza last_used_at
        Given: Dispositivo existente
        When: Se llama a update_last_used()
        Then: last_used_at se actualiza a datetime actual
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")
        device = UserDevice.create(user_id, fingerprint)
        original_last_used = device.last_used_at

        # Act - Esperar 1ms para asegurar diferencia
        import time

        time.sleep(0.001)
        device.update_last_used()

        # Assert
        assert device.last_used_at > original_last_used

    def test_update_last_used_preserves_other_fields(self):
        """
        Test: update_last_used() NO modifica otros campos
        Given: Dispositivo existente
        When: Se actualiza last_used_at
        Then: Otros campos permanecen iguales
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.2")
        device = UserDevice.create(user_id, fingerprint)

        original_id = device.id
        original_user_id = device.user_id
        original_device_name = device.device_name
        original_created_at = device.created_at
        original_is_active = device.is_active

        # Act
        device.update_last_used()

        # Assert
        assert device.id == original_id
        assert device.user_id == original_user_id
        assert device.device_name == original_device_name
        assert device.created_at == original_created_at
        assert device.is_active == original_is_active


class TestUserDeviceRevoke:
    """Tests para revoke()"""

    def test_revoke_sets_is_active_to_false(self):
        """
        Test: revoke() marca dispositivo como inactivo
        Given: Dispositivo activo
        When: Se llama a revoke()
        Then: is_active cambia a False
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")
        device = UserDevice.create(user_id, fingerprint)
        assert device.is_active is True

        # Act
        device.revoke()

        # Assert
        assert device.is_active is False

    def test_revoke_emits_device_revoked_event(self):
        """
        Test: revoke() emite DeviceRevokedEvent
        Given: Dispositivo activo
        When: Se revoca
        Then: Se emite evento DeviceRevokedEvent
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.2")
        device = UserDevice.create(user_id, fingerprint)
        device.clear_domain_events()  # Limpiar evento de creación

        # Act
        device.revoke()

        # Assert
        assert len(device.domain_events()) == 1
        event = device.domain_events()[0]
        assert isinstance(event, DeviceRevokedEvent)
        assert event.user_id == user_id
        assert event.device_id == device.id

    def test_revoke_already_revoked_device_raises_error(self):
        """
        Test: revoke() en dispositivo ya revocado lanza error
        Given: Dispositivo ya revocado
        When: Se intenta revocar nuevamente
        Then: Lanza RuntimeError
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.3")
        device = UserDevice.create(user_id, fingerprint)
        device.revoke()

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            device.revoke()

        assert "Device already revoked" in str(exc_info.value)


class TestUserDeviceReconstitute:
    """Tests para reconstitute (reconstruir desde BD)"""

    def test_reconstitute_with_all_fields(self):
        """
        Test: reconstitute() reconstruye dispositivo desde BD
        Given: Datos de BD completos
        When: Se llama a reconstitute()
        Then: Se reconstruye dispositivo correctamente
        """
        # Arrange
        device_id = UserDeviceId.generate()
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0 (Macintosh)", "192.168.1.100")
        created_at = datetime(2026, 1, 8, 14, 20, 0)
        last_used_at = datetime(2026, 1, 9, 10, 30, 0)
        is_active = True

        # Act
        device = UserDevice.reconstitute(
            id=device_id,
            user_id=user_id,
            device_name=fingerprint.device_name,
            user_agent=fingerprint.user_agent,
            ip_address=fingerprint.ip_address,
            fingerprint_hash=fingerprint.fingerprint_hash,
            is_active=is_active,
            last_used_at=last_used_at,
            created_at=created_at,
        )

        # Assert
        assert device.id == device_id
        assert device.user_id == user_id
        assert device.device_name == fingerprint.device_name
        assert device.user_agent == fingerprint.user_agent
        assert device.ip_address == fingerprint.ip_address
        assert device.fingerprint_hash == fingerprint.fingerprint_hash
        assert device.is_active is True
        assert device.last_used_at == last_used_at
        assert device.created_at == created_at

    def test_reconstitute_revoked_device(self):
        """
        Test: reconstitute() con dispositivo revocado
        Given: Datos de BD con is_active=False
        When: Se reconstruye
        Then: Dispositivo está revocado
        """
        # Arrange
        device_id = UserDeviceId.generate()
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.2")
        created_at = datetime(2026, 1, 7, 12, 10, 0)
        last_used_at = datetime(2026, 1, 8, 16, 45, 0)
        is_active = False

        # Act
        device = UserDevice.reconstitute(
            id=device_id,
            user_id=user_id,
            device_name=fingerprint.device_name,
            user_agent=fingerprint.user_agent,
            ip_address=fingerprint.ip_address,
            fingerprint_hash=fingerprint.fingerprint_hash,
            is_active=is_active,
            last_used_at=last_used_at,
            created_at=created_at,
        )

        # Assert
        assert device.is_active is False

    def test_reconstitute_does_not_emit_events(self):
        """
        Test: reconstitute() NO emite eventos de dominio
        Given: Reconstrucción desde BD
        When: Se llama a reconstitute()
        Then: No se emiten eventos (es estado pasado, no nuevo)
        """
        # Arrange
        device_id = UserDeviceId.generate()
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")

        # Act
        device = UserDevice.reconstitute(
            id=device_id,
            user_id=user_id,
            device_name=fingerprint.device_name,
            user_agent=fingerprint.user_agent,
            ip_address=fingerprint.ip_address,
            fingerprint_hash=fingerprint.fingerprint_hash,
            is_active=True,
            last_used_at=datetime.now(),
            created_at=datetime.now(),
        )

        # Assert
        assert len(device.domain_events()) == 0


class TestUserDeviceBusinessRules:
    """Tests para reglas de negocio"""

    def test_device_can_be_reused_after_revocation(self):
        """
        Test: Fingerprint puede reutilizarse tras revocación
        Given: Dispositivo revocado con fingerprint X
        When: Se crea nuevo dispositivo con mismo fingerprint
        Then: Se permite (diferente device_id)

        Note: Esto es posible por el índice único PARCIAL en BD
              (unique solo para is_active=true)
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.1")

        # Act
        device1 = UserDevice.create(user_id, fingerprint)
        device1.revoke()

        device2 = UserDevice.create(user_id, fingerprint)

        # Assert
        assert device1.id != device2.id
        assert device1.fingerprint_hash == device2.fingerprint_hash
        assert device1.is_active is False
        assert device2.is_active is True

    def test_last_used_at_never_before_created_at(self):
        """
        Test: last_used_at nunca es anterior a created_at
        Given: Dispositivo recién creado
        When: Se verifica last_used_at
        Then: last_used_at >= created_at (siempre)
        """
        # Arrange
        user_id = UserId.generate()
        fingerprint = DeviceFingerprint.create("Mozilla/5.0", "192.168.1.2")

        # Act
        device = UserDevice.create(user_id, fingerprint)

        # Assert
        assert device.last_used_at >= device.created_at
