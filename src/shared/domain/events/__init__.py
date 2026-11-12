"""
Shared Domain Events - Event System Base

Exporta las clases base para el sistema de eventos de dominio.
Estas clases serán utilizadas por todos los módulos del sistema. La
implementación en memoria vive en src.shared.infrastructure.events.
"""

from .domain_event import DomainEvent
from .event_bus import EventBus
from .event_handler import EventHandler
from .exceptions import (
    EventBusError,
    EventHandlerError,
)

__all__ = [
    # Clases base
    "DomainEvent",
    "EventBus",
    "EventBusError",
    "EventHandler",
    # Excepciones
    "EventHandlerError",
]
