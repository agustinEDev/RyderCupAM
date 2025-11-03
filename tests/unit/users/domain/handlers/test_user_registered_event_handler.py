# -*- coding: utf-8 -*-
"""
Tests unitarios para UserRegisteredEventHandler.

Verifica que el handler de registro de usuario funciona correctamente
y ejecuta todas las acciones necesarias.
"""

import pytest
from unittest.mock import patch, MagicMock
import logging

from src.users.domain.handlers.user_registered_event_handler import UserRegisteredEventHandler
from src.users.domain.events.user_registered_event import UserRegisteredEvent
from src.shared.domain.events.event_handler import EventHandler


class TestUserRegisteredEventHandler:
    """Tests para UserRegisteredEventHandler."""
    
    def test_handler_creation(self):
        """
        Test: Handler se puede crear correctamente
        Given: La clase UserRegisteredEventHandler
        When: Se instancia
        Then: Debe implementar EventHandler
        """
        handler = UserRegisteredEventHandler()
        assert isinstance(handler, EventHandler)
        assert isinstance(handler, UserRegisteredEventHandler)
    
    def test_event_type_property(self):
        """
        Test: La propiedad event_type retorna UserRegisteredEvent
        Given: Un handler de registro de usuario
        When: Se accede a la propiedad event_type
        Then: Debe retornar UserRegisteredEvent
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        
        # Act
        event_type = handler.event_type
        
        # Assert
        assert event_type == UserRegisteredEvent
    
    def test_can_handle_user_registered_event(self):
        """
        Test: Handler puede manejar UserRegisteredEvent
        Given: Un handler y un UserRegisteredEvent
        When: Se verifica si puede manejar el evento
        Then: Debe retornar True
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="123",
            email="test@test.com",
            name="Test",
            surname="User"
        )
        
        # Act
        result = handler.can_handle(event)
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_handle_user_registered_event(self):
        """
        Test: Handler procesa UserRegisteredEvent correctamente
        Given: Un handler y un evento de registro
        When: Se llama a handle()
        Then: Debe ejecutar todas las acciones sin error
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="test-user-123",
            email="juan.perez@test.com",
            name="Juan",
            surname="Pérez"
        )
        
        # Mock de métodos internos para verificar llamadas
        with patch.object(handler, '_send_welcome_email') as mock_email, \
             patch.object(handler, '_log_registration') as mock_log, \
             patch.object(handler, '_notify_external_systems') as mock_notify:
            
            # Act
            await handler.handle(event)
            
            # Assert
            mock_email.assert_called_once_with(event)
            mock_log.assert_called_once_with(event)
            mock_notify.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_send_welcome_email_logging(self):
        """
        Test: Envío de email de bienvenida se registra correctamente
        Given: Un handler y un evento
        When: Se simula el envío de email
        Then: Debe registrar la acción en el log
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="test-user-123",
            email="test@test.com",
            name="Test",
            surname="User"
        )
        
        # Act & Assert
        with patch.object(handler._logger, 'info') as mock_logger:
            await handler._send_welcome_email(event)
            
            # Verificar que se registró el log
            mock_logger.assert_called()
            args, kwargs = mock_logger.call_args
            assert "📧 Sending welcome email" in args[0]
            assert "test@test.com" in args[0]
    
    @pytest.mark.asyncio
    async def test_log_registration_logging(self):
        """
        Test: Registro de auditoría se ejecuta correctamente
        Given: Un handler y un evento
        When: Se registra el evento
        Then: Debe registrar la información de auditoría
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="test-user-123",
            email="test@test.com",
            name="Test",
            surname="User"
        )
        
        # Act & Assert
        with patch.object(handler._logger, 'info') as mock_logger:
            await handler._log_registration(event)
            
            # Verificar que se registró el log
            mock_logger.assert_called()
            args, kwargs = mock_logger.call_args
            assert "📝 Logging user registration" in args[0]
    
    @pytest.mark.asyncio
    async def test_notify_external_systems_logging(self):
        """
        Test: Notificación a sistemas externos se registra
        Given: Un handler y un evento
        When: Se notifica a sistemas externos
        Then: Debe registrar las notificaciones
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="test-user-123",
            email="test@test.com",
            name="Test",
            surname="User"
        )
        
        # Act & Assert
        with patch.object(handler._logger, 'info') as mock_logger:
            await handler._notify_external_systems(event)
            
            # Verificar que se registró el log
            mock_logger.assert_called()
            args, kwargs = mock_logger.call_args
            assert "🔔 Notifying external systems" in args[0]
    
    @pytest.mark.asyncio
    async def test_handle_logs_processing_start_and_end(self):
        """
        Test: Handler registra inicio y fin del procesamiento
        Given: Un handler y un evento
        When: Se procesa el evento
        Then: Debe registrar inicio y fin del procesamiento
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="test-user-123",
            email="ana.garcia@test.com",
            name="Ana",
            surname="García"
        )
        
        # Mock de métodos internos para evitar ejecución real
        with patch.object(handler, '_send_welcome_email'), \
             patch.object(handler, '_log_registration'), \
             patch.object(handler, '_notify_external_systems'), \
             patch.object(handler._logger, 'info') as mock_logger:
            
            # Act
            await handler.handle(event)
            
            # Assert
            # Debe haber al menos 2 llamadas: inicio y fin
            assert mock_logger.call_count >= 2
            
            # Verificar que se registra el inicio
            first_call = mock_logger.call_args_list[0]
            assert "Processing user registration for" in first_call[0][0]
            assert "Ana García" in first_call[0][0]
            assert "ana.garcia@test.com" in first_call[0][0]
            
            # Verificar que se registra el fin
            last_call = mock_logger.call_args_list[-1]
            assert "Successfully processed user registration" in last_call[0][0]


class TestUserRegisteredEventHandlerIntegration:
    """Tests de integración para UserRegisteredEventHandler."""
    
    @pytest.mark.asyncio
    async def test_complete_event_processing_flow(self):
        """
        Test: Flujo completo de procesamiento de evento
        Given: Un handler y un evento completo
        When: Se procesa el evento
        Then: Todas las acciones deben ejecutarse correctamente
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="integration-test-123",
            email="integration@test.com",
            name="Integration",
            surname="Test"
        )
        
        # Act - No debe lanzar excepción
        await handler.handle(event)
        
        # Assert - Si llegamos aquí, el flujo se completó exitosamente
        assert True  # El test pasa si no hay excepciones
    
    @pytest.mark.asyncio
    async def test_handler_with_real_event_data(self):
        """
        Test: Handler con datos reales de evento
        Given: Un handler y un evento con datos realistas
        When: Se procesa el evento
        Then: Debe manejar correctamente caracteres especiales y datos reales
        """
        # Arrange
        handler = UserRegisteredEventHandler()
        event = UserRegisteredEvent(
            user_id="real-user-456",
            email="josé.maría@español.com",
            name="José María",
            surname="González Rodríguez"
        )
        
        # Act & Assert - No debe lanzar excepción
        await handler.handle(event)
        
        # Verificar que el full_name se maneja correctamente
        assert event.full_name == "José María González Rodríguez"