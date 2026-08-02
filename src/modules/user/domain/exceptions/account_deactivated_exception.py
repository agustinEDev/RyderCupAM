"""Account Deactivated Exception - Lanzada cuando se intenta login en cuenta desactivada."""


class AccountDeactivatedException(Exception):  # noqa: N818 - Exception is intentional naming
    """
    Excepción lanzada cuando un usuario intenta hacer login en una cuenta
    desactivada por un administrador.

    Esta excepción se lanza en el Application Layer (LoginUserUseCase) cuando:
    - user.is_active es False

    Security (OWASP A07):
        - Impide el acceso a cuentas desactivadas por un admin
        - NO revela si la cuenta existe/está bloqueada por otro motivo
    """

    def __init__(self, message: str | None = None):
        self.message = message or "Account has been deactivated"
        super().__init__(self.message)
