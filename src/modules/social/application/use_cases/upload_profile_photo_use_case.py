"""Caso de Uso: Subir una foto a la galeria del perfil."""

import asyncio

from src.modules.social.application.dto.profile_photo_dto import ProfilePhotoDTO
from src.modules.social.application.exceptions import ProfileGalleryFullError
from src.modules.social.domain.entities.profile_photo import (
    MAX_PHOTOS_PER_PROFILE,
    ProfilePhoto,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.errors.user_errors import (
    AvatarUploadTooLargeError,
    UserNotFoundError,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

# Peso maximo del archivo ANTES de procesar. Rechazo temprano: evita gastar CPU
# decodificando archivos absurdos, y es el mismo tope que ya tienen los avatares.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class UploadProfilePhotoUseCase:
    """
    Sube una foto a la galeria del jugador.

    Reutiliza la tuberia de imagenes de los avatares —validacion de formato,
    tope de pixeles, correccion de orientacion EXIF y compresion— cambiando solo
    el destino: 1080 px por el lado mayor y **sin recortar a cuadrado**, porque
    una foto de una vuelta suele ser apaisada y el recorte central se comeria
    medio campo.

    **El tope es un rechazo, no una poda.** Los avatares borran el mas antiguo
    al pasarse porque son historial de una misma cosa; aqui cada foto es una
    decision del jugador, y borrarle una sin avisar para hacer sitio seria
    perderle contenido. Al llegar a diez se le dice que borre alguna.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        image_processor: IImageProcessor,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow
        self._image_processor = image_processor

    async def execute(
        self, user_id_raw: str, raw_bytes: bytes, caption: str | None = None
    ) -> ProfilePhotoDTO:
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise AvatarUploadTooLargeError(
                f"El archivo supera el tamaño máximo permitido "
                f"({MAX_UPLOAD_BYTES // (1024 * 1024)}MB)"
            )

        user_id = UserId(user_id_raw)

        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(user_id)
            if user is None or not user.is_active:
                raise UserNotFoundError(f"User with id {user_id_raw} not found")

        async with self._social_uow:
            ya_tiene = await self._social_uow.profile_photos.count_by_user(user_id)
        if ya_tiene >= MAX_PHOTOS_PER_PROFILE:
            raise ProfileGalleryFullError(
                f"La galería está llena ({MAX_PHOTOS_PER_PROFILE} fotos). "
                f"Borra alguna antes de subir otra."
            )

        # Procesado fuera de cualquier transaccion: es CPU-bound y no necesita la
        # sesion abierta. Y en un hilo aparte porque Pillow es sincrono: sin eso,
        # redimensionar una foto bloquearia TODAS las peticiones del proceso
        # mientras dura
        processed = await asyncio.to_thread(
            self._image_processor.process_gallery_image, raw_bytes
        )

        photo = ProfilePhoto.create(
            user_id=user_id, image_data=processed, content_type="image/jpeg", caption=caption
        )

        async with self._social_uow:
            await self._social_uow.profile_photos.add(photo)

        return ProfilePhotoDTO(
            id=str(photo.id.value),
            user_id=str(user_id.value),
            caption=photo.caption,
            created_at=photo.created_at,
            url=f"/api/v1/users/{user_id.value}/photos/{photo.id.value}/image",
        )
