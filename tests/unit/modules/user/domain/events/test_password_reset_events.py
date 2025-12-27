"""
Tests unitarios para los eventos de dominio de password reset.

Este archivo contiene tests que verifican:
- PasswordResetRequestedEvent: Creación y atributos
- PasswordResetCompletedEvent: Creación y atributos

Estructura:
- TestPasswordResetRequestedEvent: Tests para el evento de solicitud de reseteo
- TestPasswordResetCompletedEvent: Tests para el evento de reseteo completado
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.user.domain.events.password_reset_completed_event import (
    PasswordResetCompletedEvent,
)
from src.modules.user.domain.events.password_reset_requested_event import (
    PasswordResetRequestedEvent,
)


class TestPasswordResetRequestedEvent:
    """Tests para el evento PasswordResetRequestedEvent"""

    def test_create_password_reset_requested_event_with_all_fields(self):
        """
        Test: Crear evento con todos los campos
        Given: Todos los datos del evento incluidos
        When: Se crea una instancia de PasswordResetRequestedEvent
        Then: El evento se crea correctamente con todos los atributos
        """
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        requested_at = datetime.now()
        reset_token_expires_at = requested_at + timedelta(hours=24)
        ip_address = "192.168.1.100"
        user_agent = "Mozilla/5.0 (Test Browser)"

        # Act
        event = PasswordResetRequestedEvent(
            user_id=user_id,
            email=email,
            requested_at=requested_at,
            reset_token_expires_at=reset_token_expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Assert
        assert event.user_id == user_id
        assert event.email == email
        assert event.requested_at == requested_at
        assert event.reset_token_expires_at == reset_token_expires_at
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent

        # Verificar que heredó de DomainEvent
        assert hasattr(event, 'event_id')
        assert hasattr(event, 'occurred_on')
        assert isinstance(event.occurred_on, datetime)

    def test_create_password_reset_requested_event_without_optional_fields(self):
        """
        Test: Crear evento sin campos opcionales
        Given: Solo campos requeridos proporcionados
        When: Se crea el evento sin ip_address ni user_agent
        Then: El evento se crea con campos opcionales en None
        """
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        requested_at = datetime.now()
        reset_token_expires_at = requested_at + timedelta(hours=24)

        # Act
        event = PasswordResetRequestedEvent(
            user_id=user_id,
            email=email,
            requested_at=requested_at,
            reset_token_expires_at=reset_token_expires_at
        )

        # Assert
        assert event.user_id == user_id
        assert event.email == email
        assert event.ip_address is None
        assert event.user_agent is None

    def test_password_reset_requested_event_repr(self):
        """
        Test: Representación string del evento
        Given: Evento creado
        When: Se llama a repr()
        Then: Retorna string legible con información del evento
        """
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        requested_at = datetime.now()
        reset_token_expires_at = requested_at + timedelta(hours=24)

        event = PasswordResetRequestedEvent(
            user_id=user_id,
            email=email,
            requested_at=requested_at,
            reset_token_expires_at=reset_token_expires_at
        )

        # Act
        repr_string = repr(event)

        # Assert
        assert "PasswordResetRequestedEvent" in repr_string
        assert user_id in repr_string
        assert email in repr_string

    def test_password_reset_requested_event_has_domain_event_properties(self):
        """
        Test: Evento tiene propiedades de DomainEvent
        Given: Evento creado
        When: Se accede a propiedades heredadas
        Then: event_id y occurred_on están presentes
        """
        # Arrange & Act
        user_id = str(uuid4())
        requested_at = datetime.now()
        reset_token_expires_at = requested_at + timedelta(hours=24)

        event = PasswordResetRequestedEvent(
            user_id=user_id,
            email="test@example.com",
            requested_at=requested_at,
            reset_token_expires_at=reset_token_expires_at
        )

        # Assert
        assert event.event_id is not None
        assert isinstance(event.occurred_on, datetime)


class TestPasswordResetCompletedEvent:
    """Tests para el evento PasswordResetCompletedEvent"""

    def test_create_password_reset_completed_event_with_all_fields(self):
        """
        Test: Crear evento con todos los campos
        Given: Todos los datos del evento incluidos
        When: Se crea una instancia de PasswordResetCompletedEvent
        Then: El evento se crea correctamente con todos los atributos
        """
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        completed_at = datetime.now()
        ip_address = "192.168.1.100"
        user_agent = "Mozilla/5.0 (Test Browser)"

        # Act
        event = PasswordResetCompletedEvent(
            user_id=user_id,
            email=email,
            completed_at=completed_at,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Assert
        assert event.user_id == user_id
        assert event.email == email
        assert event.completed_at == completed_at
        assert event.ip_address == ip_address
        assert event.user_agent == user_agent

        # Verificar que heredó de DomainEvent
        assert hasattr(event, 'event_id')
        assert hasattr(event, 'occurred_on')
        assert isinstance(event.occurred_on, datetime)

    def test_create_password_reset_completed_event_without_optional_fields(self):
        """
        Test: Crear evento sin campos opcionales
        Given: Solo campos requeridos proporcionados
        When: Se crea el evento sin ip_address ni user_agent
        Then: El evento se crea con campos opcionales en None
        """
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        completed_at = datetime.now()

        # Act
        event = PasswordResetCompletedEvent(
            user_id=user_id,
            email=email,
            completed_at=completed_at
        )

        # Assert
        assert event.user_id == user_id
        assert event.email == email
        assert event.completed_at == completed_at
        assert event.ip_address is None
        assert event.user_agent is None

    def test_password_reset_completed_event_repr(self):
        """
        Test: Representación string del evento
        Given: Evento creado
        When: Se llama a repr()
        Then: Retorna string legible con información del evento
        """
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        completed_at = datetime.now()

        event = PasswordResetCompletedEvent(
            user_id=user_id,
            email=email,
            completed_at=completed_at
        )

        # Act
        repr_string = repr(event)

        # Assert
        assert "PasswordResetCompletedEvent" in repr_string
        assert user_id in repr_string
        assert email in repr_string

    def test_password_reset_completed_event_has_domain_event_properties(self):
        """
        Test: Evento tiene propiedades de DomainEvent
        Given: Evento creado
        When: Se accede a propiedades heredadas
        Then: event_id y occurred_on están presentes
        """
        # Arrange & Act
        user_id = str(uuid4())
        completed_at = datetime.now()

        event = PasswordResetCompletedEvent(
            user_id=user_id,
            email="test@example.com",
            completed_at=completed_at
        )

        # Assert
        assert event.event_id is not None
        assert isinstance(event.occurred_on, datetime)

    def test_password_reset_completed_event_timestamps_are_independent(self):
        """
        Test: completed_at y occurred_on son independientes
        Given: Evento creado con completed_at específico
        When: Se compara completed_at con occurred_on
        Then: Son timestamps diferentes (occurred_on se auto-genera)
        """
        # Arrange
        user_id = str(uuid4())
        completed_at = datetime.now() - timedelta(seconds=10)  # 10 segundos atrás

        # Act
        event = PasswordResetCompletedEvent(
            user_id=user_id,
            email="test@example.com",
            completed_at=completed_at
        )

        # Assert
        # completed_at es el que pasamos (10 segundos atrás)
        assert event.completed_at == completed_at
        # occurred_on se genera al crear el evento (ahora)
        assert event.occurred_on > completed_at
