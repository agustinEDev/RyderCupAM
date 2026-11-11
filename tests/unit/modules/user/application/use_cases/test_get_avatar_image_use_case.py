"""
Tests para GetAvatarImageUseCase.

Usa un IAvatarPresetProvider falso para no depender de los assets reales en disco.

Desde la 2.59.0 (BE #793) devuelve la imagen o None, sin excepciones para el camino
normal: sin avatar, inexistente, desactivada, bloqueado o foto perdida son el mismo
«no hay imagen», y la ruta responde 204 a todos.
"""

import pytest

from src.modules.user.application.dto.avatar_dto import ImagenDeAvatar
from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.application.use_cases.get_avatar_image_use_case import (
    GetAvatarImageUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import InvalidAvatarPresetError
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


class Bloqueos(BloqueosInterface):
    """Los bloqueos, a mano: `de[x]` son quienes bloquearon a x. Apunta las preguntas."""

    def __init__(self, de: dict | None = None):
        """Sin bloqueos salvo los que se digan."""
        self.de = de or {}
        self.preguntas: list[tuple[UserId, UserId]] = []

    async def me_bloqueo(self, quien_mira: UserId, otro: UserId) -> bool:
        """Si `otro` bloqueó a `quien_mira`; apunta la pregunta."""
        self.preguntas.append((quien_mira, otro))
        return otro in self.de.get(quien_mira, set())

    async def quienes_me_bloquearon(self, quien_mira: UserId) -> frozenset[UserId]:
        """Quienes bloquearon a `quien_mira`."""
        return frozenset(self.de.get(quien_mira, set()))


VIEWER = str(UserId.generate().value)


class FakeAvatarPresetProvider(IAvatarPresetProvider):
    def get_preset_image(self, preset_id: int) -> tuple[bytes, str]:
        return f"preset-{preset_id}-bytes".encode(), "image/jpeg"


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


async def _make_saved_user(uow: InMemoryUnitOfWork) -> User:
    user = User(
        id=UserId.generate(),
        email=Email("player@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Ana",
        last_name="García",
    )
    await uow.users.save(user)
    return user


@pytest.mark.asyncio
class TestGetAvatarImageUseCase:
    async def test_returns_preset_bytes_when_avatar_is_preset(self, uow):
        """Un preset: sus bytes."""
        user = await _make_saved_user(uow)
        user.set_preset_avatar(7)
        await uow.users.save(user)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        imagen = await use_case.execute(str(user.id.value), viewer_id=VIEWER)

        assert imagen == ImagenDeAvatar(datos=b"preset-7-bytes", tipo="image/jpeg")

    async def test_returns_upload_bytes_when_avatar_is_upload(self, uow):
        """Una foto subida: sus bytes."""
        user = await _make_saved_user(uow)
        upload = UserAvatarUpload.create(user_id=user.id, image_data=b"my-photo-bytes")
        await uow.avatar_uploads.save(upload)
        user.set_uploaded_avatar(upload.id)
        await uow.users.save(user)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        imagen = await use_case.execute(str(user.id.value), viewer_id=VIEWER)

        assert imagen == ImagenDeAvatar(datos=b"my-photo-bytes", tipo="image/jpeg")

    async def test_a3_sin_avatar_no_hay_imagen(self, uow):
        """Sin avatar: None."""
        user = await _make_saved_user(uow)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        assert await use_case.execute(str(user.id.value), viewer_id=VIEWER) is None

    async def test_a5_usuario_inexistente_no_hay_imagen(self, uow):
        """Usuario inexistente: None."""
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        assert await use_case.execute(str(UserId.generate().value), viewer_id=VIEWER) is None

    async def test_a6_foto_activa_cuyo_fichero_ya_no_existe_no_hay_imagen(self, uow):
        """La foto activa apunta a una subida que ya no está: None."""
        user = await _make_saved_user(uow)
        upload = UserAvatarUpload.create(user_id=user.id, image_data=b"my-photo-bytes")
        user.set_uploaded_avatar(upload.id)
        await uow.users.save(user)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        assert await use_case.execute(str(user.id.value), viewer_id=VIEWER) is None


# ==================== G2 y G3 (F-09, fase 3 del plan a 9) ====================


async def _otro(uow: InMemoryUnitOfWork, email: str) -> User:
    """Otro usuario guardado."""
    user = User(
        id=UserId.generate(),
        email=Email(email),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Luis",
        last_name="Mira",
    )
    await uow.users.save(user)
    return user


@pytest.mark.asyncio
class TestAvatarConBloqueoOCuentaDesactivada:
    """
    G2: si el otro me bloqueó, su avatar no existe para mí: sin imagen, como inexistente
    (la ruta responde el mismo 204). Si lo bloqueé yo, lo sigo viendo (opción A de
    Agustín, 10 nov 2026).
    G3: el de una cuenta desactivada, sin imagen.
    """

    async def _escena(self, uow):
        """El dueño con un preset y yo."""
        dueno = await _make_saved_user(uow)
        dueno.set_preset_avatar(3)
        await uow.users.save(dueno)
        yo = await _otro(uow, "yo@example.com")
        return dueno, yo

    async def test_g2_si_el_me_bloqueo_no_veo_su_avatar(self, uow):
        """
        Given: El dueño del avatar me bloqueó
        When: Pido su avatar
        Then: None, como una cuenta que no existe o sin avatar
        """
        dueno, yo = await self._escena(uow)
        bloqueos = Bloqueos({yo.id: {dueno.id}})
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        assert await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value)) is None

    async def test_g2_si_lo_bloquee_yo_veo_su_avatar(self, uow):
        """
        Given: Bloqueé al dueño del avatar
        When: Pido su avatar
        Then: Lo veo: su perfil me enseña nombre, foto y «Desbloquear»
        """
        dueno, yo = await self._escena(uow)
        bloqueos = Bloqueos({dueno.id: {yo.id}})
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        imagen = await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

        assert imagen is not None and imagen.datos == b"preset-3-bytes"

    async def test_g3_el_de_una_cuenta_desactivada_no_existe(self, uow):
        """
        Given: La cuenta del dueño está desactivada
        When: Pido su avatar
        Then: None
        """
        dueno, yo = await self._escena(uow)
        dueno.deactivate(deactivated_by_user_id=str(yo.id.value))
        await uow.users.save(dueno)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        assert await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value)) is None

    async def test_f5_sin_bloqueos_ni_quien_mira_no_se_construye(self, uow):
        """
        Given: El caso de uso
        When: Se crea sin los bloqueos o se pide sin decir quién mira
        Then: TypeError: no hay un valor por defecto que deje pasar a todos (F5)
        """
        dueno, _ = await self._escena(uow)
        with pytest.raises(TypeError):
            GetAvatarImageUseCase(uow, FakeAvatarPresetProvider())  # type: ignore[call-arg]
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())
        with pytest.raises(TypeError):
            await use_case.execute(str(dueno.id.value))  # type: ignore[call-arg]

    async def test_4_el_dueno_no_pregunta_por_bloqueos(self, uow):
        """
        Given: El dueño pide su propio avatar
        When: Se sirve
        Then: Sin preguntar por bloqueos (nadie se bloquea a sí mismo)
        """
        dueno, _ = await self._escena(uow)
        bloqueos = Bloqueos()
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        await use_case.execute(str(dueno.id.value), viewer_id=str(dueno.id.value))

        assert bloqueos.preguntas == []

    async def test_a7_un_id_de_nadie_hace_el_mismo_trabajo_que_uno_sin_avatar(self, uow):
        """
        Given: Un id que no es de nadie y una cuenta desactivada
        When: Se piden sus avatares
        Then: None, y una pregunta por bloqueos cada uno, como una cuenta sin avatar: el
              tiempo no dice si la cuenta existe (BE #793)
        """
        dueno, yo = await self._escena(uow)
        dueno.deactivate(deactivated_by_user_id=str(yo.id.value))
        await uow.users.save(dueno)
        nadie = UserId.generate()
        bloqueos = Bloqueos()
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        a = await use_case.execute(str(nadie.value), viewer_id=str(yo.id.value))
        b = await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

        assert a is None and b is None
        assert bloqueos.preguntas == [(yo.id, nadie), (yo.id, dueno.id)]

    async def test_4_el_de_otro_pregunta_una_vez(self, uow):
        """
        Given: Pido el avatar de otro, que existe
        When: Se sirve
        Then: Una sola pregunta por bloqueos, de mí hacia él
        """
        dueno, yo = await self._escena(uow)
        bloqueos = Bloqueos()
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

        assert bloqueos.preguntas == [(yo.id, dueno.id)]

    async def test_a7_sin_avatar_pregunta_por_bloqueos_como_si_me_hubiera_bloqueado(self, uow):
        """
        Given: Otro sin avatar que no me bloqueó, y otro con avatar que sí
        When: Pido sus avatares
        Then: Los dos sin imagen y con el mismo trabajo: una pregunta por bloqueos cada uno
        """
        _, yo = await self._escena(uow)
        sin_avatar = await _otro(uow, "sinavatar@example.com")
        me_bloqueo = await _otro(uow, "bloquea@example.com")
        me_bloqueo.set_preset_avatar(2)
        await uow.users.save(me_bloqueo)
        bloqueos = Bloqueos({yo.id: {me_bloqueo.id}})
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        a = await use_case.execute(str(sin_avatar.id.value), viewer_id=str(yo.id.value))
        b = await use_case.execute(str(me_bloqueo.id.value), viewer_id=str(yo.id.value))

        assert a is None and b is None
        assert bloqueos.preguntas == [(yo.id, sin_avatar.id), (yo.id, me_bloqueo.id)]


@pytest.mark.asyncio
async def test_a6_foto_borrada_con_la_referencia_a_null_no_hay_imagen(uow):
    """
    Given: La foto activa se borró y la base de datos dejó su id a NULL (ON DELETE SET
           NULL), con el origen todavía en UPLOAD
    When: Se pide el avatar
    Then: None, sin buscar una subida sin id (antes, un 500)
    """
    # Como la lee el mapper de la base de datos tras el borrado
    user = User(
        id=UserId.generate(),
        email=Email("foto-borrada@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Ana",
        last_name="García",
        avatar_source=AvatarSource.UPLOAD,
        active_avatar_upload_id=None,
    )
    await uow.users.save(user)
    use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

    assert await use_case.execute(str(user.id.value), viewer_id=VIEWER) is None


@pytest.mark.asyncio
async def test_a6_predefinido_sin_id_no_hay_imagen(uow):
    """
    Given: Una cuenta con el origen en PRESET pero sin id de cuál (un dato roto)
    When: Se pide el avatar
    Then: None, como la foto borrada (antes, un 500)
    """
    user = User(
        id=UserId.generate(),
        email=Email("preset-sin-id@example.com"),
        password=Password.from_plain_text("s3cur3P@ssw0rd!"),
        first_name="Ana",
        last_name="García",
        avatar_source=AvatarSource.PRESET,
        avatar_preset_id=None,
    )
    await uow.users.save(user)
    use_case = GetAvatarImageUseCase(uow, PresetQueFallaSinId(), Bloqueos())

    assert await use_case.execute(str(user.id.value), viewer_id=VIEWER) is None


class PresetQueFallaSinId(FakeAvatarPresetProvider):
    """Como el de verdad: sin id de preset, lanza."""

    def get_preset_image(self, preset_id):
        if preset_id is None:
            raise InvalidAvatarPresetError("sin preset")
        return super().get_preset_image(preset_id)
