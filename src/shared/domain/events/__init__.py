"""
Shared Domain Events - Event System Base

Exporta las clases base para el sistema de eventos de dominio.
Estas clases serán utilizadas por todos los módulos del sistema.
"""

from .domain_event import DomainEvent
from .event_bus import EventBus
from .event_handler import EventHandler
from .exceptions import (
    EventBusError,
    EventHandlerError,
    EventPublicationError,
    HandlerRegistrationError,
)
from .in_memory_event_bus import InMemoryEventBus

__all__ = [
    # Clases base
    "DomainEvent",
    "EventBus",
    "EventBusError",
    "EventHandler",
    # Excepciones
    "EventHandlerError",
    "EventPublicationError",
    "HandlerRegistrationError",
    # Implementaciones
    "InMemoryEventBus",
]
