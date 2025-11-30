"""
Excepciones específicas para el sistema de Domain Events.

Define las excepciones que pueden ocurrir durante el manejo
de eventos de dominio y operaciones del Event Bus.
"""

from typing import Any


class EventHandlerError(Exception):
    """
    Excepción base para errores en handlers de eventos.
    """

    def __init__(
        self,
        message: str,
        event_type: str | None = None,
        handler_type: str | None = None,
        original_error: Exception | None = None
    ):
        super().__init__(message)
        self.event_type = event_type
        self.handler_type = handler_type
        self.original_error = original_error

    def __str__(self) -> str:
        parts = [super().__str__()]

        if self.event_type:
            parts.append(f"Event Type: {self.event_type}")

        if self.handler_type:
            parts.append(f"Handler Type: {self.handler_type}")

        if self.original_error:
            parts.append(f"Original Error: {self.original_error!s}")

        return " | ".join(parts)


class EventBusError(Exception):
    """
    Excepción base para errores en el Event Bus.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{super().__str__()} | Details: {details_str}"
        return super().__str__()


class HandlerRegistrationError(EventBusError):
    """
    Error al registrar o desregistrar handlers.
    """
    pass


class EventPublicationError(EventBusError):
    """
    Error al publicar eventos.
    """
    pass
