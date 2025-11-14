# -*- coding: utf-8 -*-
"""
Tests unitarios para EventBus interface e implementación InMemoryEventBus.

Verifica el comportamiento del bus de eventos, registro de handlers
y publicación de eventos.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List

from src.shared.domain.events.event_bus import EventBus
from src.shared.domain.events.in_memory_event_bus import InMemoryEventBus
from src.shared.domain.events.event_handler import EventHandler
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.events.exceptions import EventHandlerError
from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent


class SampleEvent(DomainEvent):
    """Evento de prueba para tests."""

    def __init__(self, test_data: str):
        super().__init__()
        self.test_data = test_data


class MockEventHandler(EventHandler[SampleEvent]):
    """Handler mock para tests."""

    def __init__(self, should_fail: bool = False):
        self.handle_mock = AsyncMock()
        self.should_fail = should_fail
        self.handled_events = []

        if should_fail:
            self.handle_mock.side_effect = Exception("Handler error")

    async def handle(self, event: SampleEvent) -> None:
        self.handled_events.append(event)
        await self.handle_mock(event)

    @property
    def event_type(self) -> type[SampleEvent]:
        return SampleEvent


class MockUserRegisteredHandler(EventHandler[UserRegisteredEvent]):
    """Handler mock para UserRegisteredEvent."""
    
    def __init__(self):
        self.handle_mock = AsyncMock()
        self.handled_events = []
    
    async def handle(self, event: UserRegisteredEvent) -> None:
        self.handled_events.append(event)
        await self.handle_mock(event)
    
    @property
    def event_type(self) -> type[UserRegisteredEvent]:
        return UserRegisteredEvent


class TestEventBusInterface:
    """Tests para la interface EventBus."""
    
    def test_event_bus_is_abstract(self):
        """
        Test: EventBus es una clase abstracta
        Given: La clase EventBus
        When: Se intenta instanciar directamente
        Then: Debe lanzar TypeError
        """
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            EventBus()
    
    def test_in_memory_event_bus_implements_interface(self):
        """
        Test: InMemoryEventBus implementa la interface EventBus
        Given: La clase InMemoryEventBus
        When: Se verifica su herencia
        Then: Debe implementar EventBus
        """
        event_bus = InMemoryEventBus()
        assert isinstance(event_bus, EventBus)


class TestInMemoryEventBusBasicOperations:
    """Tests para operaciones básicas del InMemoryEventBus."""
    
    def test_event_bus_creation(self):
        """
        Test: EventBus se puede crear correctamente
        Given: La clase InMemoryEventBus
        When: Se instancia
        Then: Debe crearse correctamente
        """
        event_bus = InMemoryEventBus()
        assert isinstance(event_bus, InMemoryEventBus)
        assert event_bus.get_statistics()["total_handlers"] == 0
    
    def test_register_handler(self):
        """
        Test: Se puede registrar un handler
        Given: Un event bus y un handler
        When: Se registra el handler
        Then: Debe estar disponible para ese tipo de evento
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = MockEventHandler()
        
        # Act
        event_bus.register(handler)
        
        # Assert
        handlers = event_bus.get_handlers(SampleEvent)
        assert len(handlers) == 1
        assert handlers[0] == handler
    
    def test_register_multiple_handlers_same_event_type(self):
        """
        Test: Se pueden registrar múltiples handlers para el mismo tipo
        Given: Un event bus y varios handlers del mismo tipo
        When: Se registran todos
        Then: Todos deben estar disponibles
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()
        
        # Act
        event_bus.register(handler1)
        event_bus.register(handler2)
        
        # Assert
        handlers = event_bus.get_handlers(SampleEvent)
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers
    
    def test_register_handlers_different_event_types(self):
        """
        Test: Se pueden registrar handlers para diferentes tipos de eventos
        Given: Un event bus y handlers para diferentes eventos
        When: Se registran
        Then: Cada tipo debe tener sus handlers correspondientes
        """
        # Arrange
        event_bus = InMemoryEventBus()
        test_handler = MockEventHandler()
        user_handler = MockUserRegisteredHandler()
        
        # Act
        event_bus.register(test_handler)
        event_bus.register(user_handler)
        
        # Assert
        test_handlers = event_bus.get_handlers(SampleEvent)
        user_handlers = event_bus.get_handlers(UserRegisteredEvent)
        
        assert len(test_handlers) == 1
        assert len(user_handlers) == 1
        assert test_handlers[0] == test_handler
        assert user_handlers[0] == user_handler
    
    def test_unregister_handler(self):
        """
        Test: Se puede desregistrar un handler
        Given: Un event bus con un handler registrado
        When: Se desregistra el handler
        Then: No debe estar disponible
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = MockEventHandler()
        event_bus.register(handler)
        
        # Act
        event_bus.unregister(handler)
        
        # Assert
        handlers = event_bus.get_handlers(SampleEvent)
        assert len(handlers) == 0
    
    def test_clear_handlers(self):
        """
        Test: Se pueden limpiar todos los handlers
        Given: Un event bus con varios handlers registrados
        When: Se llama a clear_handlers()
        Then: No debe haber handlers registrados
        """
        # Arrange
        event_bus = InMemoryEventBus()
        event_bus.register(MockEventHandler())
        event_bus.register(MockUserRegisteredHandler())
        
        # Act
        event_bus.clear_handlers()
        
        # Assert
        stats = event_bus.get_statistics()
        assert stats["total_handlers"] == 0
        assert stats["total_event_types"] == 0


class TestInMemoryEventBusPublishing:
    """Tests para publicación de eventos en InMemoryEventBus."""
    
    @pytest.mark.asyncio
    async def test_publish_event_to_registered_handler(self):
        """
        Test: Evento se publica a handler registrado
        Given: Un event bus con un handler registrado
        When: Se publica un evento del tipo correcto
        Then: El handler debe procesar el evento
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = MockEventHandler()
        event_bus.register(handler)
        event = SampleEvent("test data")
        
        # Act
        await event_bus.publish(event)
        
        # Assert
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == event
        handler.handle_mock.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_publish_event_to_multiple_handlers(self):
        """
        Test: Evento se publica a múltiples handlers
        Given: Un event bus con varios handlers del mismo tipo
        When: Se publica un evento
        Then: Todos los handlers deben procesar el evento
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()
        event_bus.register(handler1)
        event_bus.register(handler2)
        event = SampleEvent("test data")
        
        # Act
        await event_bus.publish(event)
        
        # Assert
        assert len(handler1.handled_events) == 1
        assert len(handler2.handled_events) == 1
        handler1.handle_mock.assert_called_once_with(event)
        handler2.handle_mock.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_publish_event_with_no_handlers(self):
        """
        Test: Publicar evento sin handlers no causa error
        Given: Un event bus sin handlers registrados
        When: Se publica un evento
        Then: No debe lanzar excepción
        """
        # Arrange
        event_bus = InMemoryEventBus()
        event = SampleEvent("test data")
        
        # Act & Assert (no debe lanzar excepción)
        await event_bus.publish(event)
    
    @pytest.mark.asyncio
    async def test_publish_all_events(self):
        """
        Test: Se pueden publicar múltiples eventos
        Given: Un event bus con handlers y una lista de eventos
        When: Se llama a publish_all()
        Then: Todos los eventos deben ser publicados
        """
        # Arrange
        event_bus = InMemoryEventBus()
        handler = MockEventHandler()
        event_bus.register(handler)
        
        events = [
            SampleEvent("event 1"),
            SampleEvent("event 2"),
            SampleEvent("event 3")
        ]
        
        # Act
        await event_bus.publish_all(events)
        
        # Assert
        assert len(handler.handled_events) == 3
        assert handler.handle_mock.call_count == 3
    
    @pytest.mark.asyncio
    async def test_handler_error_does_not_stop_other_handlers(self):
        """
        Test: Error en un handler no detiene otros handlers
        Given: Un event bus con un handler que falla y otro que funciona
        When: Se publica un evento
        Then: El handler que funciona debe procesar el evento
        """
        # Arrange
        event_bus = InMemoryEventBus()
        failing_handler = MockEventHandler(should_fail=True)
        working_handler = MockEventHandler()
        
        event_bus.register(failing_handler)
        event_bus.register(working_handler)
        
        event = SampleEvent("test data")
        
        # Act
        await event_bus.publish(event)
        
        # Assert
        # El handler que funciona debe haber procesado el evento
        assert len(working_handler.handled_events) == 1
        working_handler.handle_mock.assert_called_once_with(event)
        
        # El handler que falla también debe haber intentado procesar
        assert len(failing_handler.handled_events) == 1
        failing_handler.handle_mock.assert_called_once_with(event)


class TestInMemoryEventBusStatistics:
    """Tests para estadísticas del InMemoryEventBus."""
    
    def test_statistics_empty_bus(self):
        """
        Test: Estadísticas de bus vacío
        Given: Un event bus sin handlers
        When: Se obtienen estadísticas
        Then: Deben reflejar el estado vacío
        """
        # Arrange
        event_bus = InMemoryEventBus()
        
        # Act
        stats = event_bus.get_statistics()
        
        # Assert
        assert stats["total_event_types"] == 0
        assert stats["total_handlers"] == 0
        assert stats["handlers_by_event_type"] == {}
    
    def test_statistics_with_handlers(self):
        """
        Test: Estadísticas con handlers registrados
        Given: Un event bus con varios handlers
        When: Se obtienen estadísticas
        Then: Deben reflejar el estado correcto
        """
        # Arrange
        event_bus = InMemoryEventBus()
        event_bus.register(MockEventHandler())
        event_bus.register(MockEventHandler())
        event_bus.register(MockUserRegisteredHandler())
        
        # Act
        stats = event_bus.get_statistics()
        
        # Assert
        assert stats["total_event_types"] == 2
        assert stats["total_handlers"] == 3
        assert stats["handlers_by_event_type"]["SampleEvent"] == 2
        assert stats["handlers_by_event_type"]["UserRegisteredEvent"] == 1