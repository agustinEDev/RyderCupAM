"""
Tests for HandicapUpdatedEvent
"""

from datetime import datetime

import pytest

from src.modules.user.domain.events.handicap_updated_event import HandicapUpdatedEvent


class TestHandicapUpdatedEventCreation:
    """Tests para la creación del evento HandicapUpdatedEvent."""

    def test_create_event_with_valid_data(self):
        """Test: Crear evento con datos válidos."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        old_handicap = 15.0
        new_handicap = 18.5
        updated_at = datetime.now()

        event = HandicapUpdatedEvent(
            user_id=user_id,
            old_handicap=old_handicap,
            new_handicap=new_handicap,
            updated_at=updated_at,
        )

        assert event.user_id == user_id
        assert event.old_handicap == old_handicap
        assert event.new_handicap == new_handicap
        assert event.updated_at == updated_at

    def test_create_event_with_none_old_handicap(self):
        """Test: Crear evento cuando el usuario no tenía hándicap previo."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=None, new_handicap=20.0, updated_at=datetime.now()
        )

        assert event.old_handicap is None
        assert event.new_handicap == 20.0

    def test_create_event_with_none_new_handicap(self):
        """Test: Crear evento cuando se elimina el hándicap."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=None, updated_at=datetime.now()
        )

        assert event.old_handicap == 15.0
        assert event.new_handicap is None

    def test_event_has_unique_event_id(self):
        """Test: Cada evento tiene un ID único."""
        event1 = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )
        event2 = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        assert event1.event_id != event2.event_id


class TestHandicapUpdatedEventProperties:
    """Tests para las propiedades del evento."""

    def test_aggregate_id_returns_user_id(self):
        """Test: aggregate_id devuelve el user_id."""
        user_id = "user-123"
        event = HandicapUpdatedEvent(
            user_id=user_id, old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        assert event.aggregate_id == user_id

    def test_has_changed_returns_true_when_different(self):
        """Test: has_changed devuelve True cuando los valores son diferentes."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        assert event.has_changed is True

    def test_has_changed_returns_false_when_same(self):
        """Test: has_changed devuelve False cuando los valores son iguales."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=15.0, updated_at=datetime.now()
        )

        assert event.has_changed is False

    def test_has_changed_with_none_values(self):
        """Test: has_changed funciona correctamente con valores None."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=None, new_handicap=None, updated_at=datetime.now()
        )

        assert event.has_changed is False

    def test_handicap_delta_calculates_difference(self):
        """Test: handicap_delta calcula la diferencia correctamente."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        assert event.handicap_delta == 3.5

    def test_handicap_delta_with_negative_change(self):
        """Test: handicap_delta con cambio negativo."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=20.0, new_handicap=15.0, updated_at=datetime.now()
        )

        assert event.handicap_delta == -5.0

    def test_handicap_delta_returns_none_when_old_is_none(self):
        """Test: handicap_delta devuelve None si old_handicap es None."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=None, new_handicap=18.5, updated_at=datetime.now()
        )

        assert event.handicap_delta is None

    def test_handicap_delta_returns_none_when_new_is_none(self):
        """Test: handicap_delta devuelve None si new_handicap es None."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=None, updated_at=datetime.now()
        )

        assert event.handicap_delta is None


class TestHandicapUpdatedEventSerialization:
    """Tests para la serialización del evento."""

    def test_to_dict_includes_handicap_change_data(self):
        """Test: to_dict incluye los datos del cambio de hándicap."""
        user_id = "123"
        old_handicap = 15.0
        new_handicap = 18.5
        updated_at = datetime.now()

        event = HandicapUpdatedEvent(
            user_id=user_id,
            old_handicap=old_handicap,
            new_handicap=new_handicap,
            updated_at=updated_at,
        )

        event_dict = event.to_dict()

        assert "handicap_change" in event_dict
        assert event_dict["handicap_change"]["user_id"] == user_id
        assert event_dict["handicap_change"]["old_value"] == old_handicap
        assert event_dict["handicap_change"]["new_value"] == new_handicap
        assert event_dict["handicap_change"]["delta"] == 3.5
        assert event_dict["handicap_change"]["updated_at"] == updated_at.isoformat()

    def test_str_representation(self):
        """Test: Representación string del evento."""
        event = HandicapUpdatedEvent(
            user_id="user-123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        event_str = str(event)
        assert "HandicapUpdatedEvent" in event_str
        assert "user-123" in event_str
        assert "15.0" in event_str
        assert "18.5" in event_str


class TestHandicapUpdatedEventImmutability:
    """Tests para verificar la inmutabilidad del evento."""

    def test_event_is_frozen(self):
        """Test: El evento es inmutable (frozen dataclass)."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            event.user_id = "456"

    def test_event_occurred_at_is_set(self):
        """Test: El evento tiene timestamp de creación."""
        event = HandicapUpdatedEvent(
            user_id="123", old_handicap=15.0, new_handicap=18.5, updated_at=datetime.now()
        )

        assert event.occurred_on is not None
        assert isinstance(event.occurred_on, datetime)
