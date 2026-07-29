"""
Upload Avatar Use Case - Application Layer

Sube una nueva foto de avatar: valida tamaño, procesa la imagen (crop+resize+compresión
vía IImageProcessor), la guarda en el historial del usuario (acotado a
AVATAR_MAX_STORED_UPLOADS, podando la más antigua si se supera) y la activa.
"""

from src.modules.user.application.dto.avatar_dto import AvatarUploadInfoDTO
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.entities.user import AVATAR_MAX_STORED_UPLOADS
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import AvatarUploadTooLargeError, UserNotFoundError
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Límite de peso del archivo ANTES de procesar (rechazo temprano, evita gastar
# CPU en decodificar/redimensionar archivos absurdamente grandes).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


class UploadAvatarUseCase:
    """Caso de uso: subir una foto propia y activarla como avatar."""

    def __init__(self, uow: UserUnitOfWorkInterface, image_processor: IImageProcessor):
        self._uow = uow
        self._image_processor = image_processor

    async def execute(self, user_id: str, raw_bytes: bytes) -> AvatarUploadInfoDTO:
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise AvatarUploadTooLargeError(
                f"El archivo supera el tamaño máximo permitido "
                f"({MAX_UPLOAD_BYTES // (1024 * 1024)}MB)"
            )

        # Procesado (validación de formato + crop/resize/compresión) fuera de la
        # transacción: es CPU-bound, no necesita la sesión de BD abierta.
        processed_bytes = self._image_processor.process_avatar_image(raw_bytes)

        async with self._uow:
            user_id_vo = UserId(user_id)
            user = await self._uow.users.find_by_id(user_id_vo)
            if not user:
                raise UserNotFoundError(f"User with id {user_id} not found")

            upload = UserAvatarUpload.create(
                user_id=user_id_vo, image_data=processed_bytes, content_type="image/jpeg"
            )
            await self._uow.avatar_uploads.save(upload)

            user.set_uploaded_avatar(upload.id)
            await self._uow.users.save(user)

            # Podar historial FIFO: el propio upload recién guardado es el más
            # reciente, así que nunca se borra a sí mismo.
            existing_uploads = await self._uow.avatar_uploads.find_by_user(user_id_vo)
            for old_upload in existing_uploads[AVATAR_MAX_STORED_UPLOADS:]:
                await self._uow.avatar_uploads.delete(old_upload.id)

        return AvatarUploadInfoDTO(
            id=upload.id.value,
            created_at=upload.created_at,
            is_active=True,
            image_url=f"/api/v1/users/me/avatar/uploads/{upload.id}/image",
        )
