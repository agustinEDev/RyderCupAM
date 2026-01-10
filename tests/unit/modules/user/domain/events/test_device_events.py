"""
Tests unitarios para los Domain Events de dispositivos.

Este archivo contiene tests que verifican:
- NewDeviceDetectedEvent
- DeviceRevokedEvent
- Estructura correcta de eventos
- Datos requeridos presentes
"""

from datetime import datetime

from src.modules.user.domain.events.device_revoked_event import DeviceRevokedEvent
from src.modules.user.domain.events.new_device_detected_event import (
    NewDeviceDetectedEvent,
)
from src.modules.user.domain.value_objects.user_device_id import UserDeviceId
from src.modules.user.domain.value_objects.user_id import UserId


class TestNewDeviceDetectedEvent:
    """Tests para NewDeviceDetectedEvent"""

    def test_event_creation_with_all_fields(self):
        """
        Test: Evento se crea con todos los campos requeridos
        Given: user_id, device_name, ip_address, user_agent
        When: Se crea NewDeviceDetectedEvent
        Then: Todos los campos están presentes
        """
        # Arrange
        user_id = UserId.generate()
        device_name = "Chrome 120.0 on macOS"
        ip_address = "192.168.1.100"
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

        # Act
        event = NewDeviceDetectedEvent(
            user_id=user_id,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Assert
        assert event.user_id == user_id
        assert event.device_name == device_name
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent
        assert isinstance(event.occurred_on, datetime)

    def test_event_has_occurred_on_timestamp(self):
        """
        Test: Evento tiene timestamp occurred_on
        Given: Creación de evento
        When: Se crea NewDeviceDetectedEvent
        Then: occurred_on es datetime cercano a now()
        """
        # Arrange
        user_id = UserId.generate()
        before = datetime.now()

        # Act
        event = NewDeviceDetectedEvent(
            user_id=user_id,
            device_name="Safari on iOS",
            ip_address="192.168.1.101",
            user_agent="Mozilla/5.0 (iPhone)",
        )
        after = datetime.now()

        # Assert
        assert before <= event.occurred_on <= after

    def test_event_representation_is_readable(self):
        """
        Test: __repr__ del evento es legible
        Given: NewDeviceDetectedEvent
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        user_id = UserId.generate()
        event = NewDeviceDetectedEvent(
            user_id=user_id,
            device_name="Firefox on Windows",
            ip_address="192.168.1.102",
            user_agent="Mozilla/5.0 (Windows NT 10.0)",
        )

        # Act
        repr_str = repr(event)

        # Assert
        assert "NewDeviceDetectedEvent" in repr_str
        assert str(user_id.value) in repr_str
        assert "Firefox on Windows" in repr_str


class TestDeviceRevokedEvent:
    """Tests para DeviceRevokedEvent"""

    def test_event_creation_with_required_fields(self):
        """
        Test: Evento se crea con campos requeridos
        Given: user_id, device_id, device_name, revoked_by_user
        When: Se crea DeviceRevokedEvent
        Then: Campos están presentes
        """
        # Arrange
        user_id = UserId.generate()
        device_id = UserDeviceId.generate()
        device_name = "Chrome on macOS"

        # Act
        event = DeviceRevokedEvent(
            user_id=user_id,
            device_id=device_id,
            device_name=device_name,
            revoked_by_user=True,
        )

        # Assert
        assert event.user_id == user_id
        assert event.device_id == device_id
        assert event.device_name == device_name
        assert event.revoked_by_user is True
        assert isinstance(event.occurred_on, datetime)

    def test_event_has_occurred_on_timestamp(self):
        """
        Test: Evento tiene timestamp occurred_on
        Given: Creación de evento
        When: Se crea DeviceRevokedEvent
        Then: occurred_on es datetime cercano a now()
        """
        # Arrange
        user_id = UserId.generate()
        device_id = UserDeviceId.generate()
        before = datetime.now()

        # Act
        event = DeviceRevokedEvent(
            user_id=user_id,
            device_id=device_id,
            device_name="Safari on iOS",
            revoked_by_user=True,
        )
        after = datetime.now()

        # Assert
        assert before <= event.occurred_on <= after

    def test_event_representation_is_readable(self):
        """
        Test: __repr__ del evento es legible
        Given: DeviceRevokedEvent
        When: Se obtiene __repr__
        Then: Contiene información útil
        """
        # Arrange
        user_id = UserId.generate()
        device_id = UserDeviceId.generate()
        event = DeviceRevokedEvent(
            user_id=user_id,
            device_id=device_id,
            device_name="Edge on Windows",
            revoked_by_user=False,
        )

        # Act
        repr_str = repr(event)

        # Assert
        assert "DeviceRevokedEvent" in repr_str
        assert str(user_id.value) in repr_str
        assert "Edge on Windows" in repr_str


class TestDeviceEventsComparison:
    """Tests para comparación entre eventos"""

    def test_different_event_types_are_not_equal(self):
        """
        Test: Eventos de tipos diferentes no son iguales
        Given: NewDeviceDetectedEvent y DeviceRevokedEvent
        When: Se comparan
        Then: No son iguales (aunque tengan mismos IDs)
        """
        # Arrange
        user_id = UserId.generate()
        device_id = UserDeviceId.generate()

        event1 = NewDeviceDetectedEvent(
            user_id=user_id,
            device_name="Chrome",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )

        event2 = DeviceRevokedEvent(
            user_id=user_id,
            device_id=device_id,
            device_name="Chrome",
            revoked_by_user=True,
        )

        # Act & Assert
        assert event1 != event2
        assert type(event1) != type(event2)
