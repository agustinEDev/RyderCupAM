"""
Cancel Email Change Use Case - Application Layer

Anula el cambio de correo pendiente de la cuenta con sesión (#749): su enlace deja de
valer y la cuenta sigue con su correo.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class CancelEmailChangeUseCase:
    """Anula el cambio de correo pendiente."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        """El caso de uso, con su unidad de trabajo."""
        self._uow = uow

    async def execute(self, user_id: str, token: str | None = None) -> UserResponseDTO:
        """
        Lo anula con la fila bloqueada; sin pendiente, no cambia nada.

        Con `token`, solo si el pendiente es el de ese token: así el 409 de último
        instante no se lleva una petición más nueva (CodeRabbit en #752).
        """
        async with self._uow:
            user = await self._uow.users.find_by_id_for_update(UserId(user_id))
            if user is None:
                raise UserNotFoundError(f"User not found: {user_id}")
            if token is None or user.pending_email_token_matches(token):
                user.cancel_email_change()
            await self._uow.users.save(user)
        return UserResponseDTO.model_validate(user)
