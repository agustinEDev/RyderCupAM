"""
El tope de la galería aguanta dos subidas a la vez (F-17).

Subir una foto contaba las que había, procesaba la imagen y luego la guardaba
en otra transacción: dos subidas con un solo hueco libre contaban las dos el
mismo número, pasaban las dos y la galería acababa con una de más. Ahora la
cuenta que decide se repite en la transacción que guarda, con la galería del
dueño bloqueada antes de contar.
"""

import asyncio
from uuid import uuid4

import pytest

from src.modules.social.application.exceptions import ProfileGalleryFullError
from src.modules.social.application.use_cases.upload_profile_photo_use_case import (
    UploadProfilePhotoUseCase,
)
from src.modules.social.domain.entities.profile_photo import MAX_PHOTOS_PER_PROFILE, ProfilePhoto
from src.modules.social.infrastructure.persistence.in_memory.in_memory_profile_photo_repository import (
    InMemoryProfilePhotoRepository,
)
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

pytestmark = pytest.mark.asyncio

RAW = b"bytes-de-una-foto"


class _RepositorioQueApunta(InMemoryProfilePhotoRepository):
    """El repositorio en memoria, apuntando el orden de lo que se le pide."""

    def __init__(self) -> None:
        super().__init__()
        self.llamadas: list[str] = []

    async def lock_gallery(self, user_id: UserId) -> None:
        """Apunta el bloqueo."""
        self.llamadas.append("bloquear")
        await super().lock_gallery(user_id)

    async def count_by_user(self, user_id: UserId) -> int:
        """Apunta la cuenta."""
        self.llamadas.append("contar")
        return await super().count_by_user(user_id)

    async def add(self, photo: ProfilePhoto) -> None:
        """Apunta el alta."""
        self.llamadas.append("guardar")
        await super().add(photo)


class _UoWQueApunta(InMemorySocialUnitOfWork):
    """La UoW en memoria con el repositorio que apunta, y sus transacciones."""

    def __init__(self) -> None:
        super().__init__()
        self._profile_photos = _RepositorioQueApunta()

    async def __aenter__(self):
        """Apunta el inicio de cada transacción."""
        self._profile_photos.llamadas.append("transaccion")
        return await super().__aenter__()


class _ProcesadorQueLlenaLaGaleria(IImageProcessor):
    """
    Mientras «procesa», otra subida llena la galería: es la carrera de verdad,
    con la foto ya aceptada por la primera cuenta y aún sin guardar.
    """

    def __init__(self, repositorio: InMemoryProfilePhotoRepository, user_id: UserId) -> None:
        self._repositorio = repositorio
        self._user_id = user_id

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        """No se usa aquí."""
        return b"avatar"

    def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        """Ocupa el último hueco libre, como haría otra subida a la vez."""
        foto = ProfilePhoto.create(
            user_id=self._user_id, image_data=b"de-la-otra", content_type="image/jpeg"
        )
        # Corre en un hilo (asyncio.to_thread): un bucle propio para el alta
        asyncio.run(self._repositorio.add(foto))
        return b"foto-procesada"


class _ProcesadorTonto(IImageProcessor):
    """Devuelve unos bytes fijos."""

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        """No se usa aquí."""
        return b"avatar"

    def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        """Unos bytes cualesquiera."""
        return b"foto-procesada"


async def _usuario_con_fotos(social_uow, user_uow, cuantas: int) -> User:
    """Un usuario activo que ya tiene `cuantas` fotos en la galería."""
    usuario = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"galeria_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(usuario)
    for _ in range(cuantas):
        await social_uow.profile_photos.add(
            ProfilePhoto.create(user_id=usuario.id, image_data=b"vieja", content_type="image/jpeg")
        )
    return usuario


async def test_si_la_galeria_se_llena_mientras_se_procesa_no_entra():
    """
    Given: una galería con un solo hueco libre
    When: otra subida ocupa ese hueco mientras esta procesa su imagen
    Then: esta se rechaza por galería llena, y la galería se queda en el tope
    """
    social_uow, user_uow = InMemorySocialUnitOfWork(), InMemoryUserUnitOfWork()
    usuario = await _usuario_con_fotos(social_uow, user_uow, MAX_PHOTOS_PER_PROFILE - 1)
    procesador = _ProcesadorQueLlenaLaGaleria(social_uow.profile_photos, usuario.id)
    caso_de_uso = UploadProfilePhotoUseCase(social_uow, user_uow, procesador)

    with pytest.raises(ProfileGalleryFullError):
        await caso_de_uso.execute(str(usuario.id.value), RAW)

    assert await social_uow.profile_photos.count_by_user(usuario.id) == MAX_PHOTOS_PER_PROFILE


async def test_bloquea_la_galeria_antes_de_la_cuenta_que_decide_y_guarda_en_esa_transaccion():
    """
    Given: una galería con sitio
    When: se sube una foto
    Then: la última transacción bloquea la galería, cuenta y guarda, en ese orden
    """
    social_uow, user_uow = _UoWQueApunta(), InMemoryUserUnitOfWork()
    usuario = await _usuario_con_fotos(social_uow, user_uow, 0)
    caso_de_uso = UploadProfilePhotoUseCase(social_uow, user_uow, _ProcesadorTonto())

    await caso_de_uso.execute(str(usuario.id.value), RAW)

    llamadas = social_uow.profile_photos.llamadas
    ultima_transaccion = llamadas[len(llamadas) - 1 - llamadas[::-1].index("transaccion") :]
    assert ultima_transaccion == ["transaccion", "bloquear", "contar", "guardar"]
