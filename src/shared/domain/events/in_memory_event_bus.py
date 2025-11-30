"""
Implementación en memoria del Event Bus.

Implementación simple y eficiente del Event Bus que mantiene
los handlers en memoria y los ejecuta de forma asíncrona.
"""

import logging
from collections import defaultdict

from .domain_event import DomainEvent
from .event_bus import EventBus
from .event_handler import EventHandler
from .exceptions import EventHandlerError

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    """
    Implementación en memoria del Event Bus.

    Características:
    - Almacena handlers en memoria agrupados por tipo de evento
    - Ejecuta handlers de forma asíncrona
    - Maneja errores de handlers de forma aislada
    - Mantiene logging detallado para debugging
    """

    def __init__(self):
        # Dict que mapea tipos de eventos a listas de handlers
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def publish(self, event: DomainEvent) -> None:
        """
        Publica un evento a todos los handlers registrados.

        Args:
            event: El evento de dominio a publicar
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        self._logger.info(
            f"Publishing event {event_type.__name__} to {len(handlers)} handlers",
            extra={
                "event_type": event_type.__name__,
                "event_id": event.event_id,
                "aggregate_id": event.aggregate_id,
                "handlers_count": len(handlers)
            }
        )

        if not handlers:
            self._logger.debug(f"No handlers registered for event type {event_type.__name__}")
            return

        # Ejecutar todos los handlers
        errors = []
        for handler in handlers:
            try:
                if handler.can_handle(event):
                    await handler.handle(event)
                    self._logger.debug(
                        f"Handler {handler.__class__.__name__} processed event {event.event_id}",
                        extra={
                            "handler_type": handler.__class__.__name__,
                            "event_id": event.event_id
                        }
                    )
                else:
                    self._logger.warning(
                        f"Handler {handler.__class__.__name__} cannot handle event {event_type.__name__}"
                    )
            except Exception as e:
                error_msg = f"Handler {handler.__class__.__name__} failed to process event {event.event_id}"
                self._logger.error(error_msg, exc_info=True)

                handler_error = EventHandlerError(
                    message=error_msg,
                    event_type=event_type.__name__,
                    handler_type=handler.__class__.__name__,
                    original_error=e
                )
                errors.append(handler_error)

        # Si hay errores, los reportamos pero no interrumpimos el flujo
        if errors:
            self._logger.error(f"Event processing completed with {len(errors)} handler errors")
            # En producción podrías enviar estos errores a un sistema de monitoreo

    async def publish_all(self, events: list[DomainEvent]) -> None:
        """
        Publica múltiples eventos en secuencia.

        Args:
            events: Lista de eventos a publicar
        """
        self._logger.info(f"Publishing batch of {len(events)} events")

        for event in events:
            try:
                await self.publish(event)
            except Exception:
                self._logger.error(
                    f"Failed to publish event {event.event_id} in batch",
                    exc_info=True
                )
                # Continuamos con los siguientes eventos

    def register(self, handler: EventHandler) -> None:
        """
        Registra un handler para un tipo específico de evento.

        Args:
            handler: El handler a registrar
        """
        event_type = handler.event_type

        # Verificar que no esté ya registrado
        if handler in self._handlers[event_type]:
            self._logger.warning(
                f"Handler {handler.__class__.__name__} already registered for {event_type.__name__}"
            )
            return

        self._handlers[event_type].append(handler)
        self._logger.info(
            f"Registered handler {handler.__class__.__name__} for event {event_type.__name__}",
            extra={
                "handler_type": handler.__class__.__name__,
                "event_type": event_type.__name__,
                "total_handlers": len(self._handlers[event_type])
            }
        )

    def unregister(self, handler: EventHandler) -> None:
        """
        Desregistra un handler específico.

        Args:
            handler: El handler a desregistrar
        """
        event_type = handler.event_type

        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            self._logger.info(
                f"Unregistered handler {handler.__class__.__name__} for event {event_type.__name__}"
            )
        else:
            self._logger.warning(
                f"Handler {handler.__class__.__name__} not found for event {event_type.__name__}"
            )

        # Limpiar la lista si está vacía
        if not self._handlers[event_type]:
            del self._handlers[event_type]

    def get_handlers(self, event_type: type[DomainEvent]) -> list[EventHandler]:
        """
        Obtiene todos los handlers registrados para un tipo de evento.

        Args:
            event_type: El tipo de evento

        Returns:
            List[EventHandler]: Lista de handlers para ese tipo de evento
        """
        return self._handlers.get(event_type, []).copy()

    def clear_handlers(self) -> None:
        """
        Limpia todos los handlers registrados.
        """
        handlers_count = sum(len(handlers) for handlers in self._handlers.values())
        self._handlers.clear()
        self._logger.info(f"Cleared all handlers ({handlers_count} total)")

    def get_statistics(self) -> dict:
        """
        Obtiene estadísticas del Event Bus.

        Returns:
            dict: Estadísticas de handlers registrados
        """
        stats = {
            "total_event_types": len(self._handlers),
            "total_handlers": sum(len(handlers) for handlers in self._handlers.values()),
            "handlers_by_event_type": {
                event_type.__name__: len(handlers)
                for event_type, handlers in self._handlers.items()
            }
        }
        return stats
