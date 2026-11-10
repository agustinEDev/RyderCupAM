"""
Tests para GetAvatarImageUseCase.

Usa un IAvatarPresetProvider falso para no depender de los assets reales en disco.
"""

import pytest

from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
from src.modules.user.application.ports.bloqueos_interface import BloqueosInterface
from src.modules.user.application.use_cases.get_avatar_image_use_case import (
    GetAvatarImageUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import AvatarNotFoundError, UserNotFoundError
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


class Bloqueos(BloqueosInterface):
    """Los bloqueos, a mano: `de[x]` son quienes bloquearon a x. Apunta las preguntas."""

    def __init__(self, de: dict | None = None):
        self.de = de or {}
        self.preguntas: list[tuple[UserId, UserId]] = []

    async def me_bloqueo(self, quien_mira: UserId, otro: UserId) -> bool:
        self.preguntas.append((quien_mira, otro))
        return otro in self.de.get(quien_mira, set())

    async def quienes_me_bloquearon(self, quien_mira: UserId) -> frozenset[UserId]:
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
        user = await _make_saved_user(uow)
        user.set_preset_avatar(7)
        await uow.users.save(user)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        image_bytes, content_type = await use_case.execute(str(user.id.value), viewer_id=VIEWER)

        assert image_bytes == b"preset-7-bytes"
        assert content_type == "image/jpeg"

    async def test_returns_upload_bytes_when_avatar_is_upload(self, uow):
        user = await _make_saved_user(uow)
        upload = UserAvatarUpload.create(user_id=user.id, image_data=b"my-photo-bytes")
        await uow.avatar_uploads.save(upload)
        user.set_uploaded_avatar(upload.id)
        await uow.users.save(user)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        image_bytes, content_type = await use_case.execute(str(user.id.value), viewer_id=VIEWER)

        assert image_bytes == b"my-photo-bytes"
        assert content_type == "image/jpeg"

    async def test_raises_when_user_has_no_avatar(self, uow):
        user = await _make_saved_user(uow)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        with pytest.raises(AvatarNotFoundError):
            await use_case.execute(str(user.id.value), viewer_id=VIEWER)

    async def test_raises_when_user_not_found(self, uow):
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value), viewer_id=VIEWER)


# ==================== G2 y G3 (F-09, fase 3 del plan a 9) ====================


async def _otro(uow: InMemoryUnitOfWork, email: str) -> User:
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
    G2: si el otro me bloqueó, su avatar no existe para mí (404 como inexistente).
    Si lo bloqueé yo, lo sigo viendo (opción A de Agustín, 10 nov 2026).
    G3: el de una cuenta desactivada, 404.
    """

    async def _escena(self, uow):
        dueno = await _make_saved_user(uow)
        dueno.set_preset_avatar(3)
        await uow.users.save(dueno)
        yo = await _otro(uow, "yo@example.com")
        return dueno, yo

    async def test_g2_si_el_me_bloqueo_no_veo_su_avatar(self, uow):
        """
        Given: El dueño del avatar me bloqueó
        When: Pido su avatar
        Then: UserNotFoundError, como una cuenta que no existe
        """
        dueno, yo = await self._escena(uow)
        bloqueos = Bloqueos({yo.id: {dueno.id}})
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

    async def test_g2_si_lo_bloquee_yo_veo_su_avatar(self, uow):
        """
        Given: Bloqueé al dueño del avatar
        When: Pido su avatar
        Then: Lo veo: su perfil me enseña nombre, foto y «Desbloquear»
        """
        dueno, yo = await self._escena(uow)
        bloqueos = Bloqueos({dueno.id: {yo.id}})
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        image_bytes, _ = await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

        assert image_bytes == b"preset-3-bytes"

    async def test_g3_el_de_una_cuenta_desactivada_no_existe(self, uow):
        """
        Given: La cuenta del dueño está desactivada
        When: Pido su avatar
        Then: UserNotFoundError
        """
        dueno, yo = await self._escena(uow)
        dueno.deactivate(deactivated_by_user_id=str(yo.id.value))
        await uow.users.save(dueno)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), Bloqueos())

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

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

    async def test_4_un_usuario_que_no_existe_no_pregunta_por_bloqueos(self, uow):
        """
        Given: Un id que no es de nadie
        When: Se pide su avatar
        Then: UserNotFoundError sin preguntar por bloqueos
        """
        _, yo = await self._escena(uow)
        bloqueos = Bloqueos()
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), bloqueos)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value), viewer_id=str(yo.id.value))

        assert bloqueos.preguntas == []

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
