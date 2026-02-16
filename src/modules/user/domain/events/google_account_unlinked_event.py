"""
Google Account Unlinked Event - Domain Layer

Evento emitido cuando un usuario desvincula su cuenta de Google.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class GoogleAccountUnlinkedEvent(DomainEvent):
    """
    Evento de dominio: Se desvinculó una cuenta de Google del usuario.

    Attributes:
        user_id: UUID del usuario
        provider: Nombre del proveedor OAuth (e.g. "google")
        unlinked_at: Timestamp de la desvinculación
    """

    user_id: str
    provider: str
    unlinked_at: datetime

    def __post_init__(self):
        super().__post_init__()
