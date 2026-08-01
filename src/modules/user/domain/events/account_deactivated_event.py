"""Account Deactivated Event - Emitido cuando un admin desactiva una cuenta."""

from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


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

    def __init__(
        self,
        user_id: str,
        deactivated_by_user_id: str,
        deactivated_at: datetime,
    ):
        super().__init__()
        self.user_id = user_id
        self.deactivated_by_user_id = deactivated_by_user_id
        self.deactivated_at = deactivated_at
