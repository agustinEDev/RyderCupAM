"""
Reauthenticate Use Case - Application Layer

Comprueba la contraseña actual de quien ya tiene sesión, antes de algo sensible como
vincular Google (BE #753, punto 2): con solo la sesión, una robada podía añadir un
Google que sobrevive a restablecer la contraseña.
"""

from src.modules.user.application.ports.security_audit_interface import ISecurityAuditLogger
from src.modules.user.application.services.registra_sin_romper import registra_sin_romper
from src.modules.user.domain.errors.user_errors import InvalidCredentialsError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.application.concurrencia.bcrypt_executor import run_bcrypt


class AccountWithoutPasswordError(ValueError):
    """La cuenta no tiene contraseña (solo Google): no hay nada que comprobar."""


class ReauthenticateUseCase:
    """La contraseña actual de la cuenta con sesión, comprobada."""

    def __init__(self, uow: UserUnitOfWorkInterface, *, security_audit: ISecurityAuditLogger):
        self._uow = uow
        self._security_audit = security_audit

    async def execute(
        self,
        user_id: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Raises:
            UserNotFoundError: si la cuenta ya no existe
            AccountWithoutPasswordError: si la cuenta no tiene contraseña
            InvalidCredentialsError: si la contraseña no es la suya
        """
        async with self._uow:
            user = await self._uow.users.find_by_id(UserId(user_id))
        if user is None:
            raise UserNotFoundError(f"User not found: {user_id}")
        if not user.has_password:
            raise AccountWithoutPasswordError("This account has no password")
        # Fuera de la transacción: bcrypt tarda (BE #283)
        if not await run_bcrypt(user.verify_password, password):
            # Al log, como un fallo de Seguridad: cada intento prueba una contraseña
            registra_sin_romper(
                "Reauthenticate",
                lambda: self._security_audit.log_security_change_failed(
                    user_id=user_id,
                    ip_address=ip_address or "unknown",
                    user_agent=user_agent or "unknown",
                    reason="wrong_current_password",
                ),
            )
            raise InvalidCredentialsError("Current password is incorrect")
