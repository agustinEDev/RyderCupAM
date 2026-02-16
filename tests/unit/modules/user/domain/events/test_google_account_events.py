"""
Tests unitarios para los Domain Events de Google OAuth.

Este archivo contiene tests que verifican:
- GoogleAccountLinkedEvent
- GoogleAccountUnlinkedEvent
- Estructura correcta de eventos
- Datos requeridos presentes
- Inmutabilidad (frozen=True)
"""

from datetime import datetime

from src.modules.user.domain.events.google_account_linked_event import (
    GoogleAccountLinkedEvent,
)
from src.modules.user.domain.events.google_account_unlinked_event import (
    GoogleAccountUnlinkedEvent,
)


class TestGoogleAccountLinkedEvent:
    """Tests para GoogleAccountLinkedEvent"""

    def test_linked_event_attributes(self):
        """
        Test: GoogleAccountLinkedEvent se crea con todos los campos
        Given: user_id, provider, provider_email, linked_at
        When: Se crea GoogleAccountLinkedEvent
        Then: Todos los campos están presentes
        """
        # Arrange
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        provider = "google"
        provider_email = "john.doe@gmail.com"
        linked_at = datetime.now()

        # Act
        event = GoogleAccountLinkedEvent(
            user_id=user_id,
            provider=provider,
            provider_email=provider_email,
            linked_at=linked_at,
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider == provider
        assert event.provider_email == provider_email
        assert event.linked_at == linked_at
        assert isinstance(event.occurred_on, datetime)

    def test_linked_event_is_frozen(self):
        """
        Test: GoogleAccountLinkedEvent es inmutable (frozen=True)
        Given: GoogleAccountLinkedEvent creado
        When: Se intenta modificar un campo
        Then: Lanza excepción FrozenInstanceError
        """
        # Arrange
        event = GoogleAccountLinkedEvent(
            user_id="user-123",
            provider="google",
            provider_email="test@gmail.com",
            linked_at=datetime.now(),
        )

        # Act & Assert
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.user_id = "new-user-id"

    def test_linked_event_has_event_metadata(self):
        """
        Test: GoogleAccountLinkedEvent tiene metadatos de DomainEvent
        Given: GoogleAccountLinkedEvent
        When: Se accede a occurred_on
        Then: Tiene timestamp automático
        """
        # Arrange
        before = datetime.now()

        # Act
        event = GoogleAccountLinkedEvent(
            user_id="user-456",
            provider="google",
            provider_email="metadata@gmail.com",
            linked_at=datetime.now(),
        )

        # Assert
        after = datetime.now()
        assert before <= event.occurred_on <= after


class TestGoogleAccountUnlinkedEvent:
    """Tests para GoogleAccountUnlinkedEvent"""

    def test_unlinked_event_attributes(self):
        """
        Test: GoogleAccountUnlinkedEvent se crea con todos los campos
        Given: user_id, provider, unlinked_at
        When: Se crea GoogleAccountUnlinkedEvent
        Then: Todos los campos están presentes
        """
        # Arrange
        user_id = "660f9500-f30c-52e5-b827-557766551111"
        provider = "google"
        unlinked_at = datetime.now()

        # Act
        event = GoogleAccountUnlinkedEvent(
            user_id=user_id,
            provider=provider,
            unlinked_at=unlinked_at,
        )

        # Assert
        assert event.user_id == user_id
        assert event.provider == provider
        assert event.unlinked_at == unlinked_at
        assert isinstance(event.occurred_on, datetime)

    def test_unlinked_event_is_frozen(self):
        """
        Test: GoogleAccountUnlinkedEvent es inmutable (frozen=True)
        Given: GoogleAccountUnlinkedEvent creado
        When: Se intenta modificar un campo
        Then: Lanza excepción FrozenInstanceError
        """
        # Arrange
        event = GoogleAccountUnlinkedEvent(
            user_id="user-789",
            provider="google",
            unlinked_at=datetime.now(),
        )

        # Act & Assert
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.provider = "facebook"

    def test_unlinked_event_has_event_metadata(self):
        """
        Test: GoogleAccountUnlinkedEvent tiene metadatos de DomainEvent
        Given: GoogleAccountUnlinkedEvent
        When: Se accede a occurred_on
        Then: Tiene timestamp automático
        """
        # Arrange
        before = datetime.now()

        # Act
        event = GoogleAccountUnlinkedEvent(
            user_id="user-abc",
            provider="google",
            unlinked_at=datetime.now(),
        )

        # Assert
        after = datetime.now()
        assert before <= event.occurred_on <= after


# Import pytest for FrozenInstanceError tests
import pytest
