"""
Shared Domain Events - Event System Base

Exporta las clases base para el sistema de eventos de dominio.
Estas clases serán utilizadas por todos los módulos del sistema.
"""

from .domain_event import DomainEvent
from .event_handler import EventHandler
from .event_bus import EventBus
from .in_memory_event_bus import InMemoryEventBus
from .exceptions import (
    EventHandlerError,
    EventBusError,
    HandlerRegistrationError,
    EventPublicationError
)

__all__ = [
    # Clases base
    "DomainEvent",
    "EventHandler",
    "EventBus",
    
    # Implementaciones
    "InMemoryEventBus",
    
    # Excepciones
    "EventHandlerError",
    "EventBusError", 
    "HandlerRegistrationError",
    "EventPublicationError",
]