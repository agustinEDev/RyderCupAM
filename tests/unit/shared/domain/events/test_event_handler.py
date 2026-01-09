"""
Tests unitarios para EventHandler interface.

Verifica que la interface EventHandler funciona correctamente
y que las implementaciones concretas cumplen el contrato.
"""

from abc import ABC
from unittest.mock import AsyncMock

import pytest

from src.modules.user.domain.events.user_registered_event import UserRegisteredEvent
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.events.event_handler import EventHandler


class SampleEvent(DomainEvent):
    """Evento de prueba para tests."""

    def __init__(self, test_data: str):
        super().__init__()
        self.test_data = test_data


class ConcreteEventHandler(EventHandler[SampleEvent]):
    """Handler concreto para tests."""

    def __init__(self):
        self.handled_events = []

    async def handle(self, event: SampleEvent) -> None:
        self.handled_events.append(event)

    @property
    def event_type(self) -> type[SampleEvent]:
        return SampleEvent


class TestEventHandlerInterface:
    """Tests para la interface EventHandler."""

    def test_event_handler_is_abstract(self):
        """
        Test: EventHandler es una clase abstracta
        Given: La clase EventHandler
        When: Se intenta instanciar directamente
        Then: Debe lanzar TypeError
        """
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            EventHandler()

    def test_event_handler_inherits_from_abc(self):
        """
        Test: EventHandler hereda de ABC
        Given: La clase EventHandler
        When: Se verifica su herencia
        Then: Debe heredar de ABC
        """
        assert issubclass(EventHandler, ABC)

    def test_concrete_handler_can_be_instantiated(self):
        """
        Test: Handler concreto puede ser instanciado
        Given: Una implementación concreta de EventHandler
        When: Se instancia
        Then: Debe crearse correctamente
        """
        handler = ConcreteEventHandler()
        assert isinstance(handler, EventHandler)
        assert isinstance(handler, ConcreteEventHandler)

    @pytest.mark.asyncio
    async def test_concrete_handler_can_handle_events(self):
        """
        Test: Handler concreto puede manejar eventos
        Given: Un handler concreto y un evento
        When: Se llama a handle()
        Then: Debe procesar el evento correctamente
        """
        # Arrange
        handler = ConcreteEventHandler()
        event = SampleEvent("test data")

        # Act
        await handler.handle(event)

        # Assert
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] == event

    def test_can_handle_with_correct_event_type(self):
        """
        Test: can_handle retorna True para el tipo correcto
        Given: Un handler y un evento del tipo correcto
        When: Se llama a can_handle()
        Then: Debe retornar True
        """
        # Arrange
        handler = ConcreteEventHandler()
        event = SampleEvent("test data")

        # Act
        result = handler.can_handle(event)

        # Assert
        assert result is True

    def test_can_handle_with_incorrect_event_type(self):
        """
        Test: can_handle retorna False para tipo incorrecto
        Given: Un handler y un evento de tipo diferente
        When: Se llama a can_handle()
        Then: Debe retornar False
        """
        # Arrange
        handler = ConcreteEventHandler()
        event = UserRegisteredEvent(
            user_id="123", email="test@test.com", first_name="Test", last_name="User"
        )

        # Act
        result = handler.can_handle(event)

        # Assert
        assert result is False

    def test_event_type_property(self):
        """
        Test: La propiedad event_type retorna el tipo correcto
        Given: Un handler concreto
        When: Se accede a la propiedad event_type
        Then: Debe retornar la clase del evento
        """
        # Arrange
        handler = ConcreteEventHandler()

        # Act
        event_type = handler.event_type

        # Assert
        assert event_type == SampleEvent
        assert issubclass(event_type, DomainEvent)


class IncompleteEventHandler(EventHandler):
    """Handler incompleto para tests de validación."""

    pass


class TestEventHandlerValidation:
    """Tests para validación de implementaciones de EventHandler."""

    def test_incomplete_handler_cannot_be_instantiated(self):
        """
        Test: Handler incompleto no puede ser instanciado
        Given: Una clase que no implementa todos los métodos abstractos
        When: Se intenta instanciar
        Then: Debe lanzar TypeError
        """
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteEventHandler()


class AsyncConcreteEventHandler(EventHandler[SampleEvent]):
    """Handler asíncrono para tests."""

    def __init__(self):
        self.handle_mock = AsyncMock()

    async def handle(self, event: SampleEvent) -> None:
        await self.handle_mock(event)

    @property
    def event_type(self) -> type[SampleEvent]:
        return SampleEvent


class TestEventHandlerAsyncBehavior:
    """Tests para comportamiento asíncrono de handlers."""

    @pytest.mark.asyncio
    async def test_async_handler_execution(self):
        """
        Test: Handler asíncrono se ejecuta correctamente
        Given: Un handler asíncrono
        When: Se llama a handle()
        Then: Debe ejecutarse de forma asíncrona
        """
        # Arrange
        handler = AsyncConcreteEventHandler()
        event = SampleEvent("async test")

        # Act
        await handler.handle(event)

        # Assert
        handler.handle_mock.assert_called_once_with(event)
