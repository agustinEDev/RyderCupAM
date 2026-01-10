"""
🔗 Integración con Domain Events - Event Logging Handler

Handler especializado para logging automático de Domain Events
con contexto enriquecido y trazabilidad completa.

Características:
- Logging automático de todos los eventos
- Metadatos enriquecidos del evento
- Contexto de correlación
- Filtrado por tipo de evento
- Formateo especializado
"""

import json
from typing import Any

from ...domain.events.domain_event import DomainEvent
from ...domain.events.event_handler import EventHandler
from ..logging.factory import get_logger
from ..logging.logger import Logger


class EventLoggingHandler(EventHandler[DomainEvent]):
    """
    Handler para logging automático de Domain Events.

    Registra todos los eventos del dominio con contexto completo,
    incluyendo metadatos, payload y información de correlación.

    Características:
    - Logging estructurado de eventos
    - Filtrado por tipo de evento
    - Nivel de logging configurable
    - Contexto enriquecido
    - Serialización segura de payloads

    Ejemplo:
        # Registrar para todos los eventos
        handler = EventLoggingHandler()
        event_bus.register(DomainEvent, handler)

        # Registrar solo para eventos específicos
        handler = EventLoggingHandler(
            event_types={UserRegisteredEvent, OrderCreatedEvent}
        )

        # Con configuración personalizada
        handler = EventLoggingHandler(
            logger_name="domain.events",
            log_level="INFO",
            include_payload=True
        )
    """

    def __init__(
        self,
        logger_name: str = "domain.events",
        log_level: str = "INFO",
        include_payload: bool = True,
        include_metadata: bool = True,
        event_types: set[type[DomainEvent]] | None = None,
        logger: Logger | None = None,
    ):
        """
        Inicializa el handler de logging.

        Args:
            logger_name: Nombre del logger a usar
            log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
            include_payload: Si incluir datos del evento
            include_metadata: Si incluir metadatos del evento
            event_types: Tipos específicos de eventos a loggear (None = todos)
            logger: Logger personalizado (opcional)
        """
        self.logger = logger or get_logger(logger_name)
        self.log_level = log_level.upper()
        self.include_payload = include_payload
        self.include_metadata = include_metadata
        self.event_types = event_types or set()

        self.logger.info(
            "🔍 Event Logging Handler iniciado",
            extra={
                "component": "EventLoggingHandler",
                "log_level": self.log_level,
                "include_payload": self.include_payload,
                "include_metadata": self.include_metadata,
                "filtered_types": len(self.event_types) if self.event_types else "all",
            },
        )

    @property
    def event_type(self) -> type[DomainEvent]:
        """Tipo de evento que maneja (todos)"""
        return DomainEvent

    def can_handle(self, event: DomainEvent) -> bool:
        """
        Determina si puede manejar el evento.

        Args:
            event: Evento a evaluar

        Returns:
            True si puede manejarlo
        """
        # Si no hay filtros, maneja todos
        if not self.event_types:
            return True

        # Verificar si el tipo del evento está en los filtros
        return any(isinstance(event, event_type) for event_type in self.event_types)

    async def handle(self, event: DomainEvent) -> None:
        """
        Maneja el evento registrándolo en el log.

        Args:
            event: Evento a loggear
        """
        try:
            # Construir datos del log
            log_data = self._build_log_data(event)

            # Crear mensaje principal
            message = self._build_message(event)

            # Loggear según nivel configurado
            self._log_with_level(message, log_data)

        except Exception as e:
            # Error en el logging no debe afectar el procesamiento
            self.logger.error(
                "❌ Error en Event Logging Handler",
                extra={
                    "error": str(e),
                    "event_type": event.__class__.__name__,
                    "event_id": str(event.event_id),
                    "component": "EventLoggingHandler",
                },
                exc_info=True,
            )

    def _build_log_data(self, event: DomainEvent) -> dict[str, Any]:
        """Construye los datos estructurados para el log"""
        log_data = {
            "component": "DomainEvent",
            "event_type": event.__class__.__name__,
            "event_id": str(event.event_id),
            "occurred_at": event.occurred_at.isoformat(),
        }

        # Metadatos del evento
        if self.include_metadata:
            log_data["metadata"] = {
                "version": event.version,
                "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
                "aggregate_type": event.aggregate_type,
                "causation_id": str(event.causation_id) if event.causation_id else None,
                "correlation_id": (
                    str(event.correlation_id) if event.correlation_id else None
                ),
            }

        # Payload del evento
        if self.include_payload:
            log_data["payload"] = self._serialize_payload(event)

        return log_data

    def _serialize_payload(self, event: DomainEvent) -> dict[str, Any]:
        """Serializa el payload del evento de manera segura"""
        try:
            # Usar to_dict si está disponible
            if hasattr(event, "to_dict"):
                event_dict = event.to_dict()
                # Remover campos que ya están en metadatos
                event_dict.pop("event_id", None)
                event_dict.pop("occurred_at", None)
                event_dict.pop("version", None)
                return event_dict

            # Fallback: serializar atributos públicos
            payload = {}
            for key, value in event.__dict__.items():
                if not key.startswith("_") and key not in [
                    "event_id",
                    "occurred_at",
                    "version",
                    "aggregate_id",
                    "aggregate_type",
                    "causation_id",
                    "correlation_id",
                ]:
                    payload[key] = self._safe_serialize_value(value)

            return payload

        except Exception as e:
            return {"serialization_error": str(e)}

    def _safe_serialize_value(self, value: Any) -> Any:
        """Serializa un valor de manera segura para JSON"""
        try:
            # Intentar serialización JSON para validar
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            # Si no es serializable, convertir a string
            return str(value)

    def _build_message(self, event: DomainEvent) -> str:
        """Construye el mensaje principal del log"""
        return (
            f"📋 Domain Event: {event.__class__.__name__} "
            f"| ID: {event.event_id} "
            f"| Aggregate: {event.aggregate_type or 'N/A'}"
        )

    def _log_with_level(self, message: str, extra: dict[str, Any]) -> None:
        """Loggea con el nivel configurado"""
        if self.log_level == "DEBUG":
            self.logger.debug(message, extra=extra)
        elif self.log_level == "INFO":
            self.logger.info(message, extra=extra)
        elif self.log_level == "WARNING":
            self.logger.warning(message, extra=extra)
        elif self.log_level == "ERROR":
            self.logger.error(message, extra=extra)
        else:
            # Fallback a INFO
            self.logger.info(message, extra=extra)


class AuditEventHandler(EventHandler[DomainEvent]):
    """
    Handler especializado para auditoría de eventos críticos.

    Mantiene un log de auditoría separado con información
    detallada para eventos que requieren trazabilidad completa.
    """

    def __init__(
        self, critical_events: set[type[DomainEvent]], logger_name: str = "audit.events"
    ):
        """
        Inicializa el handler de auditoría.

        Args:
            critical_events: Tipos de eventos críticos para auditoría
            logger_name: Nombre del logger de auditoría
        """
        self.logger = get_logger(logger_name)
        self.critical_events = critical_events

        self.logger.info(
            "🔐 Audit Event Handler iniciado",
            extra={
                "component": "AuditEventHandler",
                "critical_events": [e.__name__ for e in critical_events],
            },
        )

    @property
    def event_type(self) -> type[DomainEvent]:
        """Tipo de evento que maneja"""
        return DomainEvent

    def can_handle(self, event: DomainEvent) -> bool:
        """Solo maneja eventos críticos"""
        return any(isinstance(event, event_type) for event_type in self.critical_events)

    async def handle(self, event: DomainEvent) -> None:
        """Registra evento en log de auditoría"""
        try:
            audit_data = {
                "audit_type": "domain_event",
                "event_type": event.__class__.__name__,
                "event_id": str(event.event_id),
                "timestamp": event.occurred_at.isoformat(),
                "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
                "aggregate_type": event.aggregate_type,
                "correlation_id": (
                    str(event.correlation_id) if event.correlation_id else None
                ),
                "full_event": (
                    event.to_dict() if hasattr(event, "to_dict") else str(event)
                ),
                "severity": "HIGH",
            }

            self.logger.info(
                f"🔐 AUDIT: {event.__class__.__name__} | Aggregate: {event.aggregate_type}",
                extra=audit_data,
            )

        except Exception as e:
            self.logger.error(
                "❌ Error en Audit Event Handler",
                extra={
                    "error": str(e),
                    "event_type": event.__class__.__name__,
                    "component": "AuditEventHandler",
                },
                exc_info=True,
            )
