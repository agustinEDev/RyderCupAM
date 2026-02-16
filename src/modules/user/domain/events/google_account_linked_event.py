"""
Google Account Linked Event - Domain Layer

Evento emitido cuando un usuario vincula su cuenta de Google.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class GoogleAccountLinkedEvent(DomainEvent):
    """
    Evento de dominio: Se vinculó una cuenta de Google al usuario.

    Attributes:
        user_id: UUID del usuario
        provider: Nombre del proveedor OAuth (e.g. "google")
        provider_email: Email de la cuenta Google vinculada
        linked_at: Timestamp de la vinculación
    """

    user_id: str
    provider: str
    provider_email: str
    linked_at: datetime

    def __post_init__(self):
        super().__post_init__()
