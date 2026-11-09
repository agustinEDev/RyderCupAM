"""
Dos subidas a la galería a la vez de verdad: dos conexiones, un hueco (F-17).

Las dos pasan la primera cuenta y procesan su imagen. En la transacción que
guarda, la primera bloquea la galería del dueño, cuenta y guarda; la segunda se
queda esperando en el bloqueo hasta que la primera confirma, y entonces cuenta
ya la foto nueva: galería llena, no entra.
"""

import asyncio
import threading

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.modules.social.application.exceptions import ProfileGalleryFullError
from src.modules.social.application.use_cases.upload_profile_photo_use_case import (
    UploadProfilePhotoUseCase,
)
from src.modules.social.domain.entities.profile_photo import MAX_PHOTOS_PER_PROFILE, ProfilePhoto
from src.modules.social.infrastructure.persistence.sqlalchemy.profile_photo_repository import (
    SQLAlchemyProfilePhotoRepository,
)
from src.modules.social.infrastructure.persistence.sqlalchemy.social_unit_of_work import (
    SQLAlchemySocialUnitOfWork,
)
from src.modules.user.application.ports.image_processor_interface import IImageProcessor
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _ProcesadorQueEsperaALaOtra(IImageProcessor):
    """
    Las dos subidas salen de procesar a la vez: así las dos han pasado ya la
    primera cuenta con el mismo hueco libre, que es la carrera.
    """

    def __init__(self) -> None:
        self._barrera = threading.Barrier(2, timeout=10)

    def process_avatar_image(self, raw_bytes: bytes) -> bytes:
        """No se usa aquí."""
        return b"avatar"

    def process_gallery_image(self, raw_bytes: bytes) -> bytes:
        """Espera a que la otra subida llegue también aquí (corre en un hilo)."""
        self._barrera.wait()
        return b"foto-procesada"


class _RepositorioQueTardaEnConfirmar(SQLAlchemyProfilePhotoRepository):
    """
    Tras el alta, aguanta la transacción abierta un momento: sin bloqueo, la
    otra conexión contaría en ese rato sin ver esta foto y entraría también.
    """

    async def add(self, photo: ProfilePhoto) -> None:
        """Da de alta la foto y tarda un poco en dejar confirmar."""
        await super().add(photo)
        await asyncio.sleep(0.3)


class _SocialUoWLenta(SQLAlchemySocialUnitOfWork):
    """La UoW real del módulo social con el repositorio que tarda en confirmar."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._profile_photos = _RepositorioQueTardaEnConfirmar(session)


async def test_con_un_hueco_libre_solo_entra_una_de_dos_subidas_a_la_vez(db_session):
    """
    Given: una galería a una foto del tope
    When: el dueño sube dos fotos a la vez, cada una por su conexión
    Then: entra una, la otra se rechaza por galería llena, y quedan justo en el tope
    """
    usuario = User.create(
        first_name="Dos",
        last_name="Subidas",
        email_str="dos_subidas@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    await SQLAlchemyUserRepository(db_session).save(usuario)
    fotos = SQLAlchemyProfilePhotoRepository(db_session)
    for _ in range(MAX_PHOTOS_PER_PROFILE - 1):
        await fotos.add(
            ProfilePhoto.create(user_id=usuario.id, image_data=b"vieja", content_type="image/jpeg")
        )
    await db_session.commit()
    sesiones = async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)
    procesador = _ProcesadorQueEsperaALaOtra()

    async def subir():
        """Una subida con su propia conexión, como una petición aparte."""
        async with sesiones() as sesion:
            caso_de_uso = UploadProfilePhotoUseCase(
                _SocialUoWLenta(sesion), SQLAlchemyUnitOfWork(sesion), procesador
            )
            return await caso_de_uso.execute(str(usuario.id.value), b"foto")

    resultados = await asyncio.gather(subir(), subir(), return_exceptions=True)

    rechazadas = [r for r in resultados if isinstance(r, ProfileGalleryFullError)]
    assert len(rechazadas) == 1, resultados
    async with sesiones() as sesion:
        cuantas = await SQLAlchemyProfilePhotoRepository(sesion).count_by_user(usuario.id)
    assert cuantas == MAX_PHOTOS_PER_PROFILE
