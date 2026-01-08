"""Account Locked Exception - Lanzada cuando se intenta login en cuenta bloqueada."""

from datetime import datetime


class AccountLockedException(Exception):  # noqa: N818 - Exception is intentional naming
    """
    Excepción lanzada cuando un usuario intenta hacer login en una cuenta bloqueada
    debido a múltiples intentos fallidos de autenticación.

    Esta excepción se lanza en el Application Layer (LoginUserUseCase) cuando:
    - user.is_locked() retorna True
    - locked_until > NOW() (bloqueo activo)

    Security (OWASP A07):
        - Previene intentos adicionales durante el bloqueo
        - Mensaje incluye locked_until para informar al usuario
        - NO revelar información sensible (email, user_id)

    Attributes:
        locked_until: Timestamp cuando expira el bloqueo (30 min desde el bloqueo)
        message: Mensaje descriptivo del error

    Example:
        >>> raise AccountLockedException(
        ...     locked_until=datetime(2026, 1, 7, 15, 30, 0),
        ...     message="Account locked until 2026-01-07 15:30:00 UTC"
        ... )
    """

    def __init__(self, locked_until: datetime, message: str | None = None):
        self.locked_until = locked_until
        self.message = message or f"Account locked until {locked_until.isoformat()}"
        super().__init__(self.message)
