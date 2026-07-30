"""
Activate Uploaded Avatar Use Case - Application Layer

Activa como avatar una foto ya presente en el historial de subidas del propio
usuario, sin necesidad de volver a subirla.
"""

from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.errors.user_errors import AvatarUploadNotFoundError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId


class ActivateUploadedAvatarUseCase:
    """Caso de uso: reactivar una foto ya subida (del propio historial) como avatar."""

    def __init__(self, uow: UserUnitOfWorkInterface):
        self._uow = uow

    async def execute(self, user_id: str, upload_id: str) -> UserResponseDTO:
        async with self._uow:
            user_id_vo = UserId(user_id)
            # find_by_id_for_update: mismo bloqueo que las demás mutaciones de
            # avatar, para serializar frente a cambios concurrentes del mismo usuario.
            user = await self._uow.users.find_by_id_for_update(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            upload_id_vo = UserAvatarUploadId(upload_id)
            upload = await self._uow.avatar_uploads.find_by_id(upload_id_vo)
            if not upload or upload.user_id != user_id_vo:
                raise AvatarUploadNotFoundError(
                    f"Avatar upload {upload_id} not found for this user"
                )

            user.set_uploaded_avatar(upload.id)
            await self._uow.users.save(user)

        return UserResponseDTO.model_validate(user)
