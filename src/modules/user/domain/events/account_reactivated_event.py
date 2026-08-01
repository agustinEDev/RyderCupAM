"""Account Reactivated Event - Emitido cuando un admin reactiva una cuenta."""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class AccountReactivatedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando un administrador reactiva la cuenta
    de un usuario previamente desactivada.

    Attributes:
        user_id: ID del usuario cuya cuenta fue reactivada
        reactivated_by_user_id: ID del admin que realizó la reactivación
        reactivated_at: Timestamp de la reactivación
    """

    user_id: str
    reactivated_by_user_id: str
    reactivated_at: datetime

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id
