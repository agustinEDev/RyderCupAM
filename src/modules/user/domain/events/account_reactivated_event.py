"""Account Reactivated Event - Emitido cuando un admin reactiva una cuenta."""

from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


class AccountReactivatedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando un administrador reactiva la cuenta
    de un usuario previamente desactivada.

    Attributes:
        user_id: ID del usuario cuya cuenta fue reactivada
        reactivated_by_user_id: ID del admin que realizó la reactivación
        reactivated_at: Timestamp de la reactivación
    """

    def __init__(
        self,
        user_id: str,
        reactivated_by_user_id: str,
        reactivated_at: datetime,
    ):
        super().__init__()
        self.user_id = user_id
        self.reactivated_by_user_id = reactivated_by_user_id
        self.reactivated_at = reactivated_at
