"""
List My Avatar Uploads Use Case - Application Layer

Lista el historial de fotos subidas por el usuario autenticado (para poder
alternar entre ellas sin volver a subir), marcando cuál está activa.
"""

from src.modules.user.application.dto.avatar_dto import AvatarUploadInfoDTO
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class ListMyAvatarUploadsUseCase:
    """Caso de uso: listar el historial de fotos de avatar subidas por el usuario autenticado."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str) -> list[AvatarUploadInfoDTO]:
        async with self._uow:
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            uploads = await self._uow.avatar_uploads.find_by_user(user_id_vo)
            active_upload_id = user.active_avatar_upload_id

        return [
            AvatarUploadInfoDTO(
                id=upload.id.value,
                created_at=upload.created_at,
                is_active=active_upload_id is not None and upload.id == active_upload_id,
                image_url=f"/api/v1/users/me/avatar/uploads/{upload.id}/image",
            )
            for upload in uploads
        ]
