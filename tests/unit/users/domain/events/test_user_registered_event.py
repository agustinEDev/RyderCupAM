"""
Tests para UserRegisteredEvent

Tests unitarios que validan el comportamiento del evento de registro de usuario.
Sigue los principios de Clean Architecture y Domain Events.
"""

import pytest
from datetime import datetime
from uuid import UUID

from src.users.domain.events.user_registered_event import UserRegisteredEvent


class TestUserRegisteredEvent:
    """Test suite para UserRegisteredEvent."""
    
    def test_creates_event_with_required_data(self):
        """Evento se crea con todos los datos requeridos."""
        # Arrange & Act - Solo campos específicos, aggregate_id se genera automáticamente
        event = UserRegisteredEvent(
            user_id="user-123",
            email="juan@test.com",
            name="Juan",
            surname="Pérez"
        )
        
        # Assert
        assert event.user_id == "user-123"
        assert event.email == "juan@test.com"
        assert event.name == "Juan"
        assert event.surname == "Pérez"
        assert event.registration_method == "email"  # valor por defecto
        assert event.is_email_verified is False  # valor por defecto
        assert event.registration_ip is None  # valor por defecto
        
        # aggregate_id se genera automáticamente desde user_id
        assert event.aggregate_id == "user-123"
    
    def test_inherits_from_domain_event(self):
        """UserRegisteredEvent hereda correctamente de DomainEvent."""
        # Arrange & Act - Solo campos específicos, metadatos se generan automáticamente
        event = UserRegisteredEvent(
            user_id="user-456",
            email="maria@test.com",
            name="María",
            surname="García"
        )
        
        # Assert - Herencia y metadatos automáticos
        assert hasattr(event, 'event_id')
        assert hasattr(event, 'occurred_on')
        assert hasattr(event, 'event_version')
        assert hasattr(event, 'aggregate_id')
        assert event.event_version == 1
        assert isinstance(event.occurred_on, datetime)
        assert len(event.event_id) == 36  # UUID format
        assert event.aggregate_id == "user-456"  # Generado automáticamente
        
        # Verificar que event_id es UUID válido
        UUID(event.event_id)  # No debe lanzar excepción
    
    def test_event_is_immutable(self):
        """Evento es inmutable después de crearse."""
        # Arrange
        event = UserRegisteredEvent(
            user_id="user-789",
            email="carlos@test.com",
            name="Carlos",
            surname="López"
        )
        
        # Act & Assert - FrozenInstanceError para dataclasses frozen
        with pytest.raises(Exception, match="cannot assign to field|can't set attribute"):
            event.email = "nuevo@test.com"
        
        with pytest.raises(Exception, match="cannot assign to field|can't set attribute"):
            event.user_id = "user-999"
        
        with pytest.raises(Exception, match="cannot assign to field|can't set attribute|has no setter"):
            event.event_id = "new-id"
    
    def test_full_name_property(self):
        """Propiedad full_name concatena nombre y apellido."""
        # Test caso normal
        event1 = UserRegisteredEvent(
            user_id="user-1",
            email="test1@test.com",
            name="Ana",
            surname="Martínez"
        )
        assert event1.full_name == "Ana Martínez"
        
        # Test con nombres compuestos
        event2 = UserRegisteredEvent(
            user_id="user-2",
            email="test2@test.com",
            name="José Luis",
            surname="García Pérez"
        )
        assert event2.full_name == "José Luis García Pérez"
        
        # Test con espacios extra
        event3 = UserRegisteredEvent(
            user_id="user-3",
            email="test3@test.com",
            name="  Pedro  ",
            surname="  Sánchez  "
        )
        assert event3.full_name == "Pedro     Sánchez"  # strip() solo quita bordes
    
    def test_aggregate_id_consistency(self):
        """aggregate_id se genera automáticamente desde user_id."""
        # Arrange & Act 
        event = UserRegisteredEvent(
            user_id="user-correct",
            email="test@test.com",
            name="Test",
            surname="User"
        )
        
        # Assert - aggregate_id debe coincidir automáticamente con user_id
        assert event.aggregate_id == "user-correct"
        assert event.user_id == "user-correct"
    
    def test_registration_with_optional_fields(self):
        """Evento se puede crear con campos opcionales."""
        # Arrange & Act
        event = UserRegisteredEvent(
            user_id="user-456",
            email="premium@test.com",
            name="Premium",
            surname="User",
            registration_method="google",
            is_email_verified=True,
            registration_ip="192.168.1.100"
        )
        
        # Assert
        assert event.registration_method == "google"
        assert event.is_email_verified is True
        assert event.registration_ip == "192.168.1.100"
        assert event.aggregate_id == "user-456"  # Generado automáticamente
    
    def test_to_dict_serialization(self):
        """Serialización a diccionario incluye datos específicos del evento."""
        # Arrange
        event = UserRegisteredEvent(
            user_id="user-789",
            email="serialize@test.com",
            name="Serialize",
            surname="Test",
            registration_method="facebook",
            is_email_verified=True,
            registration_ip="10.0.0.1"
        )
        
        # Act
        result = event.to_dict()
        
        # Assert estructura base de DomainEvent
        assert 'event_id' in result
        assert 'event_type' in result
        assert 'aggregate_id' in result
        assert 'occurred_on' in result
        assert 'event_version' in result
        assert result['event_type'] == 'UserRegisteredEvent'
        assert result['aggregate_id'] == 'user-789'
        
        # Assert datos específicos del usuario
        assert 'user_data' in result
        user_data = result['user_data']
        assert user_data['user_id'] == 'user-789'
        assert user_data['email'] == 'serialize@test.com'
        assert user_data['name'] == 'Serialize'
        assert user_data['surname'] == 'Test'
        assert user_data['full_name'] == 'Serialize Test'
        
        # Assert contexto de registro
        assert 'registration_context' in result
        reg_context = result['registration_context']
        assert reg_context['method'] == 'facebook'
        assert reg_context['email_verified'] is True
        assert reg_context['ip_address'] == '10.0.0.1'
    
    def test_string_representation(self):
        """Representación string es clara y útil."""
        # Arrange
        event = UserRegisteredEvent(
            user_id="user-rep",
            email="representation@test.com",
            name="String",
            surname="Representation"
        )
        
        # Act
        str_repr = str(event)
        
        # Assert
        assert "UserRegisteredEvent" in str_repr
        assert "String Representation" in str_repr
        assert "representation@test.com" in str_repr
        assert event.event_id[:8] in str_repr
    
    def test_different_events_have_unique_ids(self):
        """Eventos diferentes tienen IDs únicos incluso con mismos datos."""
        # Act
        event1 = UserRegisteredEvent(
            user_id="user-same",
            email="same@test.com",
            name="Same",
            surname="User"
        )
        
        event2 = UserRegisteredEvent(
            user_id="user-same",
            email="same@test.com",
            name="Same",
            surname="User"
        )
        
        # Assert
        assert event1.event_id != event2.event_id
        assert event1.occurred_on != event2.occurred_on  # Timestamps diferentes
        assert event1.user_id == event2.user_id  # Datos iguales
        assert event1.email == event2.email
        assert event1.aggregate_id == event2.aggregate_id  # Ambos generados desde user_id