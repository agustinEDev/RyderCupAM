"""Caso de Uso: Borrar una foto de la galeria propia."""

from src.modules.social.application.exceptions import PhotoNotFoundError
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.user.domain.value_objects.user_id import UserId


class DeleteProfilePhotoUseCase:
    """
    Borra una foto propia.

    **Solo el dueño borra sus fotos**, ni siquiera un amigo. Y una foto de otro
    da el mismo error que una que no existe: decir "existe pero no es tuya"
    convertiria el endpoint en una forma de comprobar que ids de foto son
    reales.

    El borrado es definitivo, sin papelera: la foto ocupa espacio en la base de
    datos y guardarla "por si acaso" es justo lo que llena el disco que esta
    galeria intenta no llenar.
    """

    def __init__(self, social_uow: SocialUnitOfWorkInterface):
        self._social_uow = social_uow

    async def execute(self, user_id_raw: str, photo_id_raw: str) -> None:
        user_id = UserId(user_id_raw)
        photo_id = ProfilePhotoId(photo_id_raw)

        async with self._social_uow:
            photo = await self._social_uow.profile_photos.find_by_id(photo_id)
            if photo is None or not photo.belongs_to(user_id):
                raise PhotoNotFoundError("Photo not found")

            await self._social_uow.profile_photos.delete(photo_id)
