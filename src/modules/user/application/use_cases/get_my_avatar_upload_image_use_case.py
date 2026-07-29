"""
Get My Avatar Upload Image Use Case - Application Layer

Obtiene los bytes de una foto concreta del historial de subidas del usuario
autenticado (para renderizar las miniaturas de la galería en el frontend).
"""

from src.modules.user.domain.errors.user_errors import AvatarUploadNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId


class GetMyAvatarUploadImageUseCase:
    """Caso de uso: obtener los bytes de una foto del propio historial de subidas."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str, upload_id: str) -> tuple[bytes, str]:
        async with self._uow:
            user_id_vo = UserId(user_id)
            upload_id_vo = UserAvatarUploadId(upload_id)
            upload = await self._uow.avatar_uploads.find_by_id(upload_id_vo)
            if not upload or upload.user_id != user_id_vo:
                raise AvatarUploadNotFoundError(
                    f"Avatar upload {upload_id} not found for this user"
                )

            return upload.image_data, upload.content_type
