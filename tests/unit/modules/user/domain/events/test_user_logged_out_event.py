"""
Tests para UserLoggedOutEvent

Tests unitarios para el evento de dominio UserLoggedOutEvent.
"""

import pytest
from datetime import datetime

from src.modules.user.domain.events.user_logged_out_event import UserLoggedOutEvent


class TestUserLoggedOutEvent:
    """Tests para el evento UserLoggedOutEvent."""

    def test_user_logged_out_event_creation_with_required_fields(self):
        """
        Test: Creación de evento con campos requeridos
        Given: Datos mínimos requeridos
        When: Se crea un UserLoggedOutEvent
        Then: Se crea correctamente con valores por defecto
        """
        # Arrange
        user_id = "test-user-123"
        logged_out_at = datetime.now()

        # Act
        event = UserLoggedOutEvent(
            user_id=user_id,
            logged_out_at=logged_out_at
        )

        # Assert
        assert event.user_id == user_id
        assert event.logged_out_at == logged_out_at
        assert event.token_used is None
        assert event.ip_address is None
        assert event.user_agent is None
        assert event.aggregate_id == user_id

    def test_user_logged_out_event_creation_with_all_fields(self):
        """
        Test: Creación de evento con todos los campos opcionales
        Given: Todos los datos incluyendo opcionales
        When: Se crea un UserLoggedOutEvent
        Then: Se crea correctamente con todos los valores
        """
        # Arrange
        user_id = "test-user-456"
        logged_out_at = datetime.now()
        token_used = "jwt-token-123"
        ip_address = "192.168.1.1"
        user_agent = "Mozilla/5.0 Test"

        # Act
        event = UserLoggedOutEvent(
            user_id=user_id,
            logged_out_at=logged_out_at,
            token_used=token_used,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Assert
        assert event.user_id == user_id
        assert event.logged_out_at == logged_out_at
        assert event.token_used == token_used
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent
        assert event.aggregate_id == user_id

    def test_user_logged_out_event_is_frozen(self):
        """
        Test: El evento es inmutable (frozen)
        Given: Un evento creado
        When: Se intenta modificar un atributo
        Then: Lanza excepción de inmutabilidad
        """
        # Arrange
        event = UserLoggedOutEvent(
            user_id="test-user",
            logged_out_at=datetime.now()
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            event.user_id = "modified-user"  # type: ignore

    def test_user_logged_out_event_str_representation(self):
        """
        Test: Representación string del evento
        Given: Un evento creado
        When: Se convierte a string
        Then: Contiene información relevante
        """
        # Arrange
        user_id = "test-user-789"
        logged_out_at = datetime.now()
        token_used = "jwt-token-abc"

        event = UserLoggedOutEvent(
            user_id=user_id,
            logged_out_at=logged_out_at,
            token_used=token_used
        )

        # Act
        str_repr = str(event)

        # Assert
        assert "UserLoggedOutEvent" in str_repr
        assert user_id in str_repr
        assert "token_present=True" in str_repr

    def test_user_logged_out_event_str_representation_without_token(self):
        """
        Test: Representación string del evento sin token
        Given: Un evento sin token
        When: Se convierte a string
        Then: Indica que no hay token presente
        """
        # Arrange
        event = UserLoggedOutEvent(
            user_id="test-user",
            logged_out_at=datetime.now()
        )

        # Act
        str_repr = str(event)

        # Assert
        assert "token_present=False" in str_repr

    def test_user_logged_out_event_to_dict(self):
        """
        Test: Conversión del evento a diccionario
        Given: Un evento con todos los campos
        When: Se convierte a diccionario
        Then: Contiene todos los campos serializados correctamente
        """
        # Arrange
        user_id = "test-user-dict"
        logged_out_at = datetime.now()
        token_used = "jwt-token-dict"
        ip_address = "10.0.0.1"
        user_agent = "Test Agent"

        event = UserLoggedOutEvent(
            user_id=user_id,
            logged_out_at=logged_out_at,
            token_used=token_used,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Act
        event_dict = event.to_dict()

        # Assert
        assert event_dict["event_type"] == "UserLoggedOutEvent"
        assert event_dict["aggregate_id"] == user_id
        assert event_dict["user_id"] == user_id
        assert event_dict["logged_out_at"] == logged_out_at.isoformat()
        assert event_dict["token_used"] == token_used
        assert event_dict["ip_address"] == ip_address
        assert event_dict["user_agent"] == user_agent
        assert "occurred_on" in event_dict

    def test_user_logged_out_event_has_occurred_at_timestamp(self):
        """
        Test: El evento tiene timestamp de ocurrencia automático
        Given: Se crea un evento
        When: Se verifica el timestamp
        Then: Tiene occurred_at automático y reciente
        """
        # Arrange
        before_creation = datetime.now()
        
        # Act
        event = UserLoggedOutEvent(
            user_id="test-user",
            logged_out_at=datetime.now()
        )
        
        after_creation = datetime.now()

        # Assert
        assert hasattr(event, 'occurred_on')
        assert before_creation <= event.occurred_on <= after_creation