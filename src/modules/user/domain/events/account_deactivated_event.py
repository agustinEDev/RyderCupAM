"""Account Deactivated Event - Emitido cuando un admin desactiva una cuenta."""

from dataclasses import dataclass
from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


@dataclass(frozen=True)
class AccountDeactivatedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando un administrador desactiva la cuenta
    de un usuario desde el panel de administración.

    Security (OWASP A09):
        - Evento de auditoría: registra quién desactivó y cuándo
        - La cuenta desactivada no puede iniciar sesión (ver User.deactivate())

    Attributes:
        user_id: ID del usuario cuya cuenta fue desactivada
        deactivated_by_user_id: ID del admin que realizó la desactivación
        deactivated_at: Timestamp de la desactivación
    """

    user_id: str
    deactivated_by_user_id: str
    deactivated_at: datetime

    @property
    def aggregate_id(self) -> str:
        """El ID del agregado es el ID del usuario."""
        return self.user_id
