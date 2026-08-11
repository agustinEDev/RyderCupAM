"""
Tests de la galeria de fotos del perfil (BE #177).

Tres reglas gobiernan estos tests: las fotos son **solo para amigos**, el tope
**rechaza** en vez de borrar la mas antigua, y solo el dueño borra las suyas.
"""

from uuid import uuid4

import pytest

from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    PhotoNotFoundError,
    ProfileGalleryFullError,
    ProfileNotVisibleError,
)
from src.modules.social.application.use_cases.delete_profile_photo_use_case import (
    DeleteProfilePhotoUseCase,
)
from src.modules.social.application.use_cases.get_profile_gallery_use_case import (
    GetProfileGalleryUseCase,
)
from src.modules.social.application.use_cases.get_profile_photo_image_use_case import (
    GetProfilePhotoImageUseCase,
)
from src.modules.social.application.use_cases.upload_profile_photo_use_case import (
    MAX_UPLOAD_BYTES,
    UploadProfilePhotoUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.entities.profile_photo import MAX_PHOTOS_PER_PROFILE
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import AvatarUploadTooLargeError
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

RAW = b"bytes-de-una-foto"


class _FakeImageProcessor(IImageProcessor):
    """Evita depender de Pillow: la tuberia real se prueba en su propio test."""

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        return b"avatar-procesado"

    def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        return b"foto-procesada-1080px"


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


async def _create_user(user_uow) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"foto_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _hacer_amigos(social_uow, a: User, b: User) -> None:
    friendship = Friendship.create(
        id=FriendshipId(uuid4()), requester_id=a.id, addressee_id=b.id
    )
    friendship.accept()
    async with social_uow:
        await social_uow.friendships.add(friendship)


def _subir(social_uow, user_uow):
    return UploadProfilePhotoUseCase(social_uow, user_uow, _FakeImageProcessor())


class TestSubir:
    async def test_sube_una_foto_procesada(self, social_uow, user_uow):
        """Given una imagen / When se sube / Then se guarda ya procesada."""
        ana = await _create_user(user_uow)

        foto = await _subir(social_uow, user_uow).execute(
            str(ana.id.value), RAW, caption="En Valderrama"
        )

        assert foto.caption == "En Valderrama"
        assert foto.url.endswith("/image")
        async with social_uow:
            guardada = await social_uow.profile_photos.find_by_id(
                (await social_uow.profile_photos.find_metadata_by_user(ana.id))[0].id
            )
        assert guardada.image_data == b"foto-procesada-1080px"

    async def test_un_pie_en_blanco_es_lo_mismo_que_no_tener_pie(self, social_uow, user_uow):
        """Given un caption de espacios / When se sube / Then se guarda como None."""
        ana = await _create_user(user_uow)

        foto = await _subir(social_uow, user_uow).execute(str(ana.id.value), RAW, caption="   ")

        assert foto.caption is None

    async def test_el_tope_rechaza_en_vez_de_borrar_la_mas_antigua(
        self, social_uow, user_uow
    ):
        """
        Given una galeria llena / When se sube otra / Then se rechaza y **no se
        pierde ninguna**: cada foto es una decision del jugador, no historial.
        """
        ana = await _create_user(user_uow)
        use_case = _subir(social_uow, user_uow)
        for i in range(MAX_PHOTOS_PER_PROFILE):
            await use_case.execute(str(ana.id.value), RAW, caption=f"foto {i}")

        with pytest.raises(ProfileGalleryFullError):
            await use_case.execute(str(ana.id.value), RAW)

        async with social_uow:
            assert await social_uow.profile_photos.count_by_user(ana.id) == MAX_PHOTOS_PER_PROFILE

    async def test_un_archivo_enorme_se_rechaza_antes_de_procesarlo(
        self, social_uow, user_uow
    ):
        """Given un archivo por encima del tope / When se sube / Then se rechaza."""
        ana = await _create_user(user_uow)

        with pytest.raises(AvatarUploadTooLargeError):
            await _subir(social_uow, user_uow).execute(
                str(ana.id.value), b"x" * (MAX_UPLOAD_BYTES + 1)
            )


class TestVerLaGaleria:
    async def test_un_amigo_ve_la_galeria(self, social_uow, user_uow):
        """Given un amigo con fotos / When pido su galeria / Then la veo."""
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        await _hacer_amigos(social_uow, ana, luis)
        await _subir(social_uow, user_uow).execute(str(luis.id.value), RAW)

        galeria = await GetProfileGalleryUseCase(social_uow, user_uow).execute(
            str(ana.id.value), str(luis.id.value)
        )

        assert galeria.total == 1

    async def test_un_desconocido_no_ve_la_galeria(self, social_uow, user_uow):
        """Given dos sin amistad / When se pide la galeria / Then se rechaza."""
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        await _subir(social_uow, user_uow).execute(str(luis.id.value), RAW)

        with pytest.raises(ActivityNotVisibleError):
            await GetProfileGalleryUseCase(social_uow, user_uow).execute(
                str(ana.id.value), str(luis.id.value)
            )

    async def test_el_listado_no_lleva_las_imagenes(self, social_uow, user_uow):
        """
        Given una galeria / When se lista / Then vienen los enlaces, no los bytes:
        diez fotos son casi cuatro megas que el navegador pide aparte.
        """
        ana = await _create_user(user_uow)
        await _subir(social_uow, user_uow).execute(str(ana.id.value), RAW)

        galeria = await GetProfileGalleryUseCase(social_uow, user_uow).execute(
            str(ana.id.value), str(ana.id.value)
        )

        assert "image_data" not in galeria.photos[0].model_dump()

    async def test_dice_cuantas_fotos_caben_todavia(self, social_uow, user_uow):
        """Given 3 fotos / When se pide la galeria / Then quedan 7 huecos."""
        ana = await _create_user(user_uow)
        for _ in range(3):
            await _subir(social_uow, user_uow).execute(str(ana.id.value), RAW)

        galeria = await GetProfileGalleryUseCase(social_uow, user_uow).execute(
            str(ana.id.value), str(ana.id.value)
        )

        assert galeria.remaining_slots == MAX_PHOTOS_PER_PROFILE - 3

    async def test_un_jugador_que_no_existe_da_otro_error(self, social_uow, user_uow):
        """Given un id inventado / When se pide su galeria / Then no existe."""
        ana = await _create_user(user_uow)

        with pytest.raises(ProfileNotVisibleError):
            await GetProfileGalleryUseCase(social_uow, user_uow).execute(
                str(ana.id.value), str(uuid4())
            )


class TestServirLaImagen:
    async def test_el_etag_es_estable_para_la_misma_foto(self, social_uow, user_uow):
        """
        Given una foto / When se pide dos veces / Then el ETag es el mismo: es lo
        que permite al navegador quedarsela y no volver a bajarla.
        """
        ana = await _create_user(user_uow)
        foto = await _subir(social_uow, user_uow).execute(str(ana.id.value), RAW)
        use_case = GetProfilePhotoImageUseCase(social_uow)

        una = await use_case.execute(str(ana.id.value), str(ana.id.value), foto.id)
        otra = await use_case.execute(str(ana.id.value), str(ana.id.value), foto.id)

        assert una.etag == otra.etag
        assert una.etag.startswith('"') and una.etag.endswith('"')

    async def test_un_desconocido_no_baja_la_imagen(self, social_uow, user_uow):
        """Given una foto de un extraño / When se pide la imagen / Then se rechaza."""
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        foto = await _subir(social_uow, user_uow).execute(str(luis.id.value), RAW)

        with pytest.raises(ActivityNotVisibleError):
            await GetProfilePhotoImageUseCase(social_uow).execute(
                str(ana.id.value), str(luis.id.value), foto.id
            )

    async def test_una_foto_que_no_es_del_dueno_de_la_ruta_no_se_sirve(
        self, social_uow, user_uow
    ):
        """
        Given la foto de un amigo pedida bajo la ruta de otro amigo / When se
        pide / Then no se sirve: sin esta comprobacion, un id valido se colaria
        por la ruta de cualquiera y se saltaria el guard de su dueño real.
        """
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        marta = await _create_user(user_uow)
        await _hacer_amigos(social_uow, ana, luis)
        await _hacer_amigos(social_uow, ana, marta)
        de_marta = await _subir(social_uow, user_uow).execute(str(marta.id.value), RAW)

        with pytest.raises(PhotoNotFoundError):
            await GetProfilePhotoImageUseCase(social_uow).execute(
                str(ana.id.value), str(luis.id.value), de_marta.id
            )


class TestBorrar:
    async def test_el_dueno_borra_su_foto(self, social_uow, user_uow):
        """Given una foto propia / When se borra / Then desaparece."""
        ana = await _create_user(user_uow)
        foto = await _subir(social_uow, user_uow).execute(str(ana.id.value), RAW)

        await DeleteProfilePhotoUseCase(social_uow).execute(str(ana.id.value), foto.id)

        async with social_uow:
            assert await social_uow.profile_photos.count_by_user(ana.id) == 0

    async def test_un_amigo_no_puede_borrar_mis_fotos(self, social_uow, user_uow):
        """Given una foto mia / When un amigo intenta borrarla / Then no puede."""
        ana = await _create_user(user_uow)
        luis = await _create_user(user_uow)
        await _hacer_amigos(social_uow, ana, luis)
        foto = await _subir(social_uow, user_uow).execute(str(ana.id.value), RAW)

        with pytest.raises(PhotoNotFoundError):
            await DeleteProfilePhotoUseCase(social_uow).execute(str(luis.id.value), foto.id)

        async with social_uow:
            assert await social_uow.profile_photos.count_by_user(ana.id) == 1

    async def test_borrar_hace_sitio_para_subir_otra(self, social_uow, user_uow):
        """Given una galeria llena / When se borra una / Then ya cabe otra."""
        ana = await _create_user(user_uow)
        subir = _subir(social_uow, user_uow)
        fotos = [
            await subir.execute(str(ana.id.value), RAW)
            for _ in range(MAX_PHOTOS_PER_PROFILE)
        ]

        await DeleteProfilePhotoUseCase(social_uow).execute(str(ana.id.value), fotos[0].id)
        await subir.execute(str(ana.id.value), RAW)

        async with social_uow:
            assert await social_uow.profile_photos.count_by_user(ana.id) == MAX_PHOTOS_PER_PROFILE
