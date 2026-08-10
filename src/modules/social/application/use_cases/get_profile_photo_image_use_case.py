"""Caso de Uso: Servir la imagen de una foto del perfil."""

from dataclasses import dataclass

from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    PhotoNotFoundError,
)
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.social.domain.value_objects.profile_photo_id import ProfilePhotoId
from src.modules.user.domain.value_objects.user_id import UserId


@dataclass(frozen=True)
class PhotoImage:
    """La imagen y lo que hace falta para cachearla."""

    data: bytes
    content_type: str
    etag: str


class GetProfilePhotoImageUseCase:
    """
    Los bytes de una foto, con lo necesario para no volver a pedirlos.

    **El ETag es el id de la foto**, y puede serlo porque la imagen es
    inmutable: no se edita una foto, se borra y se sube otra con otro id. Unos
    bytes servidos bajo un id nunca van a cambiar, asi que el navegador puede
    quedarselos indefinidamente.

    Esto es lo que decide si la galeria es viable: cada foto la sirve el backend
    ocupando un worker, y un perfil con diez fotos son diez peticiones. Sin
    cache, cada visita al perfil las pide las diez otra vez.
    """

    def __init__(self, social_uow: SocialUnitOfWorkInterface):
        self._social_uow = social_uow

    async def execute(
        self, viewer_id_raw: str, owner_id_raw: str, photo_id_raw: str
    ) -> PhotoImage:
        viewer_id = UserId(viewer_id_raw)
        owner_id = UserId(owner_id_raw)
        photo_id = ProfilePhotoId(photo_id_raw)

        async with self._social_uow:
            if viewer_id != owner_id and not await self._social_uow.friendships.are_friends(
                viewer_id, owner_id
            ):
                raise ActivityNotVisibleError("Only friends can see this player's photos")

            photo = await self._social_uow.profile_photos.find_by_id(photo_id)

        # Se comprueba tambien que la foto sea de quien dice la ruta: sin esto,
        # un id de foto valido serviria desde la ruta de cualquier amigo y se
        # saltaria el guard del dueño real
        if photo is None or not photo.belongs_to(owner_id):
            raise PhotoNotFoundError("Photo not found")

        return PhotoImage(
            data=photo.image_data,
            content_type=photo.content_type,
            # Entrecomillado porque un ETag es una cadena entrecomillada segun
            # la norma HTTP, y sin las comillas algunos proxies lo descartan
            etag=f'"{photo.id.value}"',
        )
