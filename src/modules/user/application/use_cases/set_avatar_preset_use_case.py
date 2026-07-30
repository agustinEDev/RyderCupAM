"""
Set Avatar Preset Use Case - Application Layer

Activa uno de los 10 presets de avatar como avatar activo del usuario.
"""

from src.modules.user.application.dto.avatar_dto import SetAvatarPresetRequestDTO
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class SetAvatarPresetUseCase:
    """Caso de uso: activar un preset de avatar predefinido para el usuario autenticado."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str, request: SetAvatarPresetRequestDTO) -> UserResponseDTO:
        async with self._uow:
            user_id_vo = UserId(user_id)
            # find_by_id_for_update: mismo bloqueo de fila que UploadAvatarUseCase,
            # para que un cambio de avatar concurrente (subida/activar histórico/
            # quitar) con esta misma operación se serialice de forma consistente.
            user = await self._uow.users.find_by_id_for_update(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            user.set_preset_avatar(request.preset_id)
            await self._uow.users.save(user)

        return UserResponseDTO.model_validate(user)
