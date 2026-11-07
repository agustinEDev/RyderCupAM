"""
Reauthenticate Use Case - Application Layer

Comprueba la contraseña actual de quien ya tiene sesión, antes de algo sensible como
vincular Google (BE #753, punto 2): con solo la sesión, una robada podía añadir un
Google que sobrevive a restablecer la contraseña.
"""

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

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str, password: str) -> None:
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
            raise InvalidCredentialsError("Current password is incorrect")
