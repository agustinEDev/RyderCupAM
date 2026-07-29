"""
Get Avatar Image Use Case - Application Layer

Obtiene los bytes de la imagen del avatar ACTIVO de un usuario cualquiera
(propio o de otro usuario) — resuelve internamente si toca leer un preset
(disco) o una foto subida (BD), para que el frontend pueda mostrar el avatar
de cualquier usuario con una única URL, sin conocer el origen.
"""

from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.domain.errors.user_errors import AvatarNotFoundError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
from src.modules.user.domain.value_objects.user_id import UserId


class GetAvatarImageUseCase:
    """Caso de uso: obtener los bytes del avatar activo de un usuario."""

    def __init__(self, uow: UserUnitOfWorkInterface, preset_provider: IAvatarPresetProvider):
        self._uow = uow
        self._preset_provider = preset_provider

    async def execute(self, user_id: str) -> tuple[bytes, str]:
        async with self._uow:
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            if user.avatar_source == AvatarSource.NONE:
                raise AvatarNotFoundError(f"User {user_id} has no avatar set")

            if user.avatar_source == AvatarSource.PRESET:
                return self._preset_provider.get_preset_image(user.avatar_preset_id)

            # AvatarSource.UPLOAD
            upload = await self._uow.avatar_uploads.find_by_id(user.active_avatar_upload_id)
            if not upload:
                raise AvatarNotFoundError(f"User {user_id} avatar upload no longer exists")

            return upload.image_data, upload.content_type
