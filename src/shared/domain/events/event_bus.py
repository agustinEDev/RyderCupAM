"""
Event Bus Interface para Domain Events.

Este archivo define la interfaz del bus de eventos que permite
publicar eventos y registrar handlers de forma desacoplada.
"""

from abc import ABC, abstractmethod

from .domain_event import DomainEvent
from .event_handler import EventHandler


class EventBus(ABC):
    """
    Interfaz del bus de eventos para Domain Events.

    El Event Bus es responsable de:
    - Registrar handlers para tipos específicos de eventos
    - Publicar eventos a todos los handlers registrados
    - Manejar errores de handlers de forma aislada
    - Mantener el desacoplamiento entre productores y consumidores
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """
        Publica un evento a todos los handlers registrados.

        Args:
            event: El evento de dominio a publicar

        Note:
            Los errores en handlers individuales no deben afectar
            la ejecución de otros handlers.
        """
        pass

    @abstractmethod
    async def publish_all(self, events: list[DomainEvent]) -> None:
        """
        Publica múltiples eventos en secuencia.

        Args:
            events: Lista de eventos a publicar
        """
        pass

    @abstractmethod
    def register(self, handler: EventHandler) -> None:
        """
        Registra un handler para un tipo específico de evento.

        Args:
            handler: El handler a registrar
        """
        pass

    @abstractmethod
    def unregister(self, handler: EventHandler) -> None:
        """
        Desregistra un handler específico.

        Args:
            handler: El handler a desregistrar
        """
        pass

    @abstractmethod
    def get_handlers(self, event_type: type[DomainEvent]) -> list[EventHandler]:
        """
        Obtiene todos los handlers registrados para un tipo de evento.

        Args:
            event_type: El tipo de evento

        Returns:
            List[EventHandler]: Lista de handlers para ese tipo de evento
        """
        pass

    @abstractmethod
    def clear_handlers(self) -> None:
        """
        Limpia todos los handlers registrados.

        Útil para testing y reinicio del sistema.
        """
        pass
