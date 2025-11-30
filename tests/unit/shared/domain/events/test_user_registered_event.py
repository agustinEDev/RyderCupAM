from datetime import datetime

import pytest

from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
from src.shared.domain.events.domain_event import DomainEvent


class TestUserRegisteredEvent:
    """Test suite para UserRegisteredEvent."""

    def test_creates_event_with_required_data(self):
        """Evento se crea con todos los datos requeridos."""
        event = UserRegisteredEvent(
            user_id="user-123",
            email="juan@test.com",
            first_name="Juan",
            last_name="Pérez"
        )
        assert event.user_id == "user-123"
        assert event.email == "juan@test.com"
        assert event.first_name == "Juan"
        assert event.last_name == "Pérez"
        assert event.aggregate_id == "user-123"

    def test_inherits_from_domain_event(self):
        """UserRegisteredEvent hereda correctamente de DomainEvent."""
        event = UserRegisteredEvent(
            user_id="user-456",
            email="maria@test.com",
            first_name="María",
            last_name="García"
        )
        assert isinstance(event, DomainEvent)
        assert hasattr(event, 'event_id')
        assert isinstance(event.occurred_on, datetime)

    def test_event_is_immutable(self):
        """Evento es inmutable después de crearse."""
        event = UserRegisteredEvent(
            user_id="user-789",
            email="carlos@test.com",
            first_name="Carlos",
            last_name="López"
        )
        with pytest.raises(Exception, match="cannot assign to field|can't set attribute"):
            event.email = "nuevo@test.com"

    def test_full_name_property(self):
        """Propiedad full_name concatena nombre y apellido."""
        event = UserRegisteredEvent(
            user_id="user-1",
            email="test1@test.com",
            first_name="Ana",
            last_name="Martínez"
        )
        assert event.full_name == "Ana Martínez"

    def test_aggregate_id_consistency(self):
        """aggregate_id se genera automáticamente desde user_id."""
        event = UserRegisteredEvent(
            user_id="user-correct",
            email="test@test.com",
            first_name="Test",
            last_name="User"
        )
        assert event.aggregate_id == "user-correct"

    def test_registration_with_optional_fields(self):
        """Evento se puede crear con campos opcionales."""
        event = UserRegisteredEvent(
            user_id="user-456",
            email="premium@test.com",
            first_name="Premium",
            last_name="User",
            registration_method="google",
            is_email_verified=True,
            registration_ip="192.168.1.100"
        )
        assert event.registration_method == "google"
        assert event.is_email_verified is True
        assert event.registration_ip == "192.168.1.100"

    def test_to_dict_serialization(self):
        """Serialización a diccionario incluye datos específicos del evento."""
        event = UserRegisteredEvent(
            user_id="user-789",
            email="serialize@test.com",
            first_name="Serialize",
            last_name="Test"
        )
        result = event.to_dict()
        user_data = result['user_data']
        assert user_data['first_name'] == 'Serialize'
        assert user_data['last_name'] == 'Test'

    def test_string_representation(self):
        """Representación string es clara y útil."""
        event = UserRegisteredEvent(
            user_id="user-rep",
            email="representation@test.com",
            first_name="String",
            last_name="Representation"
        )
        str_repr = str(event)
        assert "String Representation" in str_repr
        assert "representation@test.com" in str_repr

    def test_different_events_have_unique_ids(self):
        """Eventos diferentes tienen IDs únicos incluso con mismos datos."""
        event1 = UserRegisteredEvent(
            user_id="user-same",
            email="same@test.com",
            first_name="Same",
            last_name="User"
        )
        event2 = UserRegisteredEvent(
            user_id="user-same",
            email="same@test.com",
            first_name="Same",
            last_name="User"
        )
        assert event1.event_id != event2.event_id
