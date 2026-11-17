"""
Shared Domain Events

La clase base DomainEvent y los eventos de seguridad que la extienden
(security_events), que registra el log de seguridad.
"""

from .domain_event import DomainEvent

__all__ = [
    "DomainEvent",
]
