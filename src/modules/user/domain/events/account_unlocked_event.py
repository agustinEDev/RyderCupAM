"""Account Unlocked Event - Emitido cuando un admin desbloquea una cuenta."""

from datetime import datetime

from src.shared.domain.events.domain_event import DomainEvent


class AccountUnlockedEvent(DomainEvent):
    """
    Evento de dominio emitido cuando una cuenta de usuario es desbloqueada
    manualmente por un administrador.

    Este evento se dispara cuando:
    - Un admin ejecuta User.unlock(unlocked_by_user_id)
    - failed_login_attempts es reseteado a 0
    - locked_until es eliminado (None)

    Security (OWASP A09):
        - Severity: MEDIUM (acción administrativa legítima)
        - Auditoría de quién desbloqueó la cuenta
        - Puede requerir notificación al usuario

    Attributes:
        user_id: ID del usuario cuya cuenta fue desbloqueada
        unlocked_by: ID del admin que realizó el desbloqueo
        unlocked_at: Timestamp del desbloqueo
        previous_locked_until: Timestamp original de expiración del bloqueo
        previous_failed_attempts: Número de intentos fallidos antes del desbloqueo
    """

    def __init__(
        self,
        user_id: str,
        unlocked_by: str,
        unlocked_at: datetime,
        previous_locked_until: datetime | None,
        previous_failed_attempts: int,
    ):
        super().__init__()
        self.user_id = user_id
        self.unlocked_by = unlocked_by
        self.unlocked_at = unlocked_at
        self.previous_locked_until = previous_locked_until
        self.previous_failed_attempts = previous_failed_attempts
