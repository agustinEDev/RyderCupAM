"""
Remove Avatar Use Case - Application Layer

Quita el avatar activo del usuario (vuelve al placeholder por defecto).
No borra el historial de fotos subidas.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class RemoveAvatarUseCase:
    """Caso de uso: quitar el avatar activo del usuario autenticado."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str) -> UserResponseDTO:
        async with self._uow:
            user_id_vo = UserId(user_id)
            # find_by_id_for_update: mismo bloqueo que las demás mutaciones de
            # avatar, para serializar frente a cambios concurrentes del mismo usuario.
            user = await self._uow.users.find_by_id_for_update(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            user.clear_avatar()
            await self._uow.users.save(user)

        return UserResponseDTO.model_validate(user)
