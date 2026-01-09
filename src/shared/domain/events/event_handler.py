"""
Event Handler Interface para Domain Events.

Este archivo define la interfaz base que deben implementar todos los
handlers de eventos de dominio, siguiendo principios de Clean Architecture.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .domain_event import DomainEvent

# Type variable para permitir handlers específicos para tipos de eventos
EventType = TypeVar("EventType", bound=DomainEvent)


class EventHandler(Generic[EventType], ABC):  # noqa: UP046 - Generic syntax for Python 3.11 compatibility
    """
    Interfaz base para todos los handlers de eventos de dominio.

    Los handlers son responsables de manejar los efectos secundarios
    que deben ocurrir cuando se publican eventos de dominio.

    Ejemplos de uso:
    - Enviar emails de bienvenida cuando se registra un usuario
    - Actualizar vistas de lectura (CQRS)
    - Integrar con sistemas externos
    - Logging y auditoría
    """

    @abstractmethod
    async def handle(self, event: EventType) -> None:
        """
        Maneja un evento de dominio específico.

        Args:
            event: El evento de dominio a manejar

        Raises:
            EventHandlerError: Si ocurre un error durante el manejo del evento
        """
        pass

    @property
    @abstractmethod
    def event_type(self) -> type[EventType]:
        """
        Retorna el tipo de evento que maneja este handler.

        Returns:
            type: La clase del evento que maneja
        """
        pass

    def can_handle(self, event: DomainEvent) -> bool:
        """
        Verifica si este handler puede manejar el evento dado.

        Args:
            event: El evento a verificar

        Returns:
            bool: True si puede manejar el evento, False en caso contrario
        """
        return isinstance(event, self.event_type)
