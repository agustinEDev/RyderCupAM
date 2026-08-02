"""Caso de Uso: (Des)activar una cuenta de usuario (panel de administración)."""

from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class AdminSetUserActiveUseCase:
    """
    Desactiva o reactiva la cuenta de un usuario (solo Admin).

    Una cuenta desactivada no puede iniciar sesión pero conserva todos sus
    datos (torneos, partidas, amistades) intactos — acción reversible.
    """

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id_str: str, is_active: bool, actor_user_id: str) -> None:
        if not is_active and user_id_str == actor_user_id:
            raise ValueError("Admins cannot deactivate their own account")

        user_id = UserId(user_id_str)

        async with self._uow:
            user = await self._uow.users.find_by_id(user_id)
            if not user:
                raise UserNotFoundError(f"User not found: {user_id_str}")

            if is_active:
                if not user.is_active:
                    user.reactivate(reactivated_by_user_id=actor_user_id)
            elif user.is_active:
                user.deactivate(deactivated_by_user_id=actor_user_id)

            await self._uow.users.save(user)
