"""Caso de Uso: Ver la galeria de fotos de un jugador."""

from src.modules.social.application.dto.profile_photo_dto import (
    ProfileGalleryResponseDTO,
    ProfilePhotoDTO,
)
from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    ProfileNotVisibleError,
)
from src.modules.social.domain.entities.profile_photo import MAX_PHOTOS_PER_PROFILE
from src.modules.social.domain.repositories.social_unit_of_work_interface import (
    SocialUnitOfWorkInterface,
)
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class GetProfileGalleryUseCase:
    """
    Las fotos de un jugador, **solo para sus amigos**.

    Mismo reparto que la actividad: la ficha de alguien la ve cualquiera, pero
    lo que hay detras es entre amigos. Y el mismo trato a los errores — 403 si
    no sois amigos, 404 si el jugador no esta — porque a estas alturas su
    existencia no es ningun secreto.

    El listado **no lleva las imagenes**, solo por donde bajarlas. Diez fotos son
    casi cuatro megas: mandarlas dentro del listado obligaria a esperar a que
    llegaran todas para pintar nada, cuando el navegador puede pedirlas por
    separado, en paralelo, y guardarlas en cache para la proxima visita.
    """

    def __init__(
        self,
        social_uow: SocialUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._social_uow = social_uow
        self._user_uow = user_uow

    async def execute(self, viewer_id_raw: str, target_id_raw: str) -> ProfileGalleryResponseDTO:
        viewer_id = UserId(viewer_id_raw)
        target_id = UserId(target_id_raw)

        async with self._user_uow:
            target = await self._user_uow.users.find_by_id(target_id)
            if target is None or not target.is_active:
                raise ProfileNotVisibleError("Profile not found")

        if viewer_id != target_id:
            async with self._social_uow:
                if not await self._social_uow.friendships.are_friends(viewer_id, target_id):
                    raise ActivityNotVisibleError("Only friends can see this player's photos")

        async with self._social_uow:
            fotos = await self._social_uow.profile_photos.find_metadata_by_user(target_id)

        return ProfileGalleryResponseDTO(
            photos=[
                ProfilePhotoDTO(
                    id=str(foto.id.value),
                    user_id=str(target_id.value),
                    caption=foto.caption,
                    created_at=foto.created_at,
                    url=f"/api/v1/users/{target_id.value}/photos/{foto.id.value}/image",
                )
                for foto in fotos
            ],
            total=len(fotos),
            # Solo tiene sentido para uno mismo, pero se calcula igual: al cliente
            # le sale gratis y evita una segunda llamada para saber si puede subir
            remaining_slots=max(0, MAX_PHOTOS_PER_PROFILE - len(fotos)),
        )
