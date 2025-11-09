"""
Tests unitarios para UserLoggedInEvent

Verifica que el evento de dominio UserLoggedInEvent funcione correctamente
siguiendo los principios de Domain-Driven Design.
"""

import pytest
from datetime import datetime
from src.modules.user.domain.events.user_logged_in_event import UserLoggedInEvent


class TestUserLoggedInEvent:
    """Test suite para UserLoggedInEvent."""

    def test_create_user_logged_in_event_with_required_fields(self):
        """
        Test: Crear evento con campos requeridos únicamente.
        
        Verifica que se puede crear un UserLoggedInEvent con solo los campos
        obligatorios (user_id y logged_in_at).
        """
        # Arrange
        user_id = "user-123"
        logged_in_at = datetime(2024, 1, 15, 10, 30, 45)
        
        # Act
        event = UserLoggedInEvent(
            user_id=user_id,
            logged_in_at=logged_in_at
        )
        
        # Assert
        assert event.user_id == user_id
        assert event.logged_in_at == logged_in_at
        assert event.ip_address is None
        assert event.user_agent is None
        assert event.session_id is None
        assert event.login_method is None

    def test_create_user_logged_in_event_with_all_fields(self):
        """
        Test: Crear evento con todos los campos opcionales.
        
        Verifica que el evento puede almacenar información adicional
        como IP, user agent, session ID y método de login.
        """
        # Arrange
        user_id = "user-456"
        logged_in_at = datetime(2024, 1, 15, 14, 20, 0)
        ip_address = "192.168.1.100"
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        session_id = "session-abc123"
        login_method = "email"
        
        # Act
        event = UserLoggedInEvent(
            user_id=user_id,
            logged_in_at=logged_in_at,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            login_method=login_method
        )
        
        # Assert
        assert event.user_id == user_id
        assert event.logged_in_at == logged_in_at
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent
        assert event.session_id == session_id
        assert event.login_method == login_method

    def test_event_is_immutable(self):
        """
        Test: El evento es inmutable (frozen=True).
        
        Verifica que una vez creado el evento, sus campos no pueden
        ser modificados (principio de inmutabilidad de eventos de dominio).
        """
        # Arrange
        event = UserLoggedInEvent(
            user_id="user-789",
            logged_in_at=datetime.now()
        )
        
        # Act & Assert
        with pytest.raises(Exception):  # FrozenInstanceError en dataclasses
            event.user_id = "different-user"
        
        with pytest.raises(Exception):
            event.logged_in_at = datetime.now()

    def test_event_has_automatic_metadata(self):
        """
        Test: El evento genera metadatos automáticamente.
        
        Verifica que DomainEvent base añade automáticamente:
        - event_id único
        - occurred_on timestamp
        - event_version
        - aggregate_id (basado en user_id)
        """
        # Arrange & Act
        event = UserLoggedInEvent(
            user_id="user-metadata-test",
            logged_in_at=datetime.now()
        )
        
        # Assert - Metadatos generados automáticamente
        assert hasattr(event, '_event_id')
        assert hasattr(event, '_occurred_on')
        assert hasattr(event, '_event_version')
        assert hasattr(event, '_aggregate_id')
        
        assert event._event_id is not None
        assert event._occurred_on is not None
        assert event._event_version == 1
        assert event._aggregate_id == "user-metadata-test"

    def test_str_representation(self):
        """
        Test: Representación string del evento.
        
        Verifica que __str__ produce una representación útil para
        logging y debugging sin exponer datos sensibles.
        """
        # Arrange
        user_id = "user-string-test"
        logged_in_at = datetime(2024, 1, 15, 16, 45, 30)
        ip_address = "10.0.0.1"
        login_method = "email"
        
        event = UserLoggedInEvent(
            user_id=user_id,
            logged_in_at=logged_in_at,
            ip_address=ip_address,
            login_method=login_method
        )
        
        # Act
        str_repr = str(event)
        
        # Assert
        assert "UserLoggedInEvent" in str_repr
        assert user_id in str_repr
        assert "2024-01-15T16:45:30" in str_repr
        assert ip_address in str_repr
        assert login_method in str_repr

    def test_to_dict_serialization(self):
        """
        Test: Serialización del evento a diccionario.
        
        Verifica que to_dict() incluye tanto los datos del evento
        como los metadatos base para almacenamiento/comunicación.
        """
        # Arrange
        user_id = "user-dict-test"
        logged_in_at = datetime(2024, 1, 15, 18, 0, 0)
        ip_address = "172.16.0.1"
        user_agent = "TestClient/1.0"
        session_id = "sess-xyz789"
        login_method = "email"
        
        event = UserLoggedInEvent(
            user_id=user_id,
            logged_in_at=logged_in_at,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            login_method=login_method
        )
        
        # Act
        event_dict = event.to_dict()
        
        # Assert - Datos del evento
        assert event_dict["user_id"] == user_id
        assert event_dict["logged_in_at"] == "2024-01-15T18:00:00"
        assert event_dict["ip_address"] == ip_address
        assert event_dict["user_agent"] == user_agent
        assert event_dict["session_id"] == session_id
        assert event_dict["login_method"] == login_method
        
        # Assert - Metadatos base
        assert "event_id" in event_dict
        assert "occurred_on" in event_dict
        assert "event_version" in event_dict
        assert "aggregate_id" in event_dict
        
        assert event_dict["event_id"] is not None
        assert event_dict["occurred_on"] is not None
        assert event_dict["event_version"] == 1
        assert event_dict["aggregate_id"] == user_id

    def test_events_have_unique_ids(self):
        """
        Test: Cada evento tiene un ID único.
        
        Verifica que dos eventos creados por separado tengan
        diferentes event_id para garantizar unicidad.
        """
        # Arrange & Act
        event1 = UserLoggedInEvent(
            user_id="user-1",
            logged_in_at=datetime.now()
        )
        
        event2 = UserLoggedInEvent(
            user_id="user-2", 
            logged_in_at=datetime.now()
        )
        
        # Assert
        assert event1._event_id != event2._event_id
        assert event1._aggregate_id != event2._aggregate_id