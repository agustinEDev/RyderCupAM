"""
Tests para GetAvatarImageUseCase.

Usa un IAvatarPresetProvider falso para no depender de los assets reales en disco.
"""

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.application.ports.avatar_preset_provider_interface import (
    IAvatarPresetProvider,
)
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
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider())

        image_bytes, content_type = await use_case.execute(str(user.id.value))

        assert image_bytes == b"preset-7-bytes"
        assert content_type == "image/jpeg"

    async def test_returns_upload_bytes_when_avatar_is_upload(self, uow):
        user = await _make_saved_user(uow)
        upload = UserAvatarUpload.create(user_id=user.id, image_data=b"my-photo-bytes")
        await uow.avatar_uploads.save(upload)
        user.set_uploaded_avatar(upload.id)
        await uow.users.save(user)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider())

        image_bytes, content_type = await use_case.execute(str(user.id.value))

        assert image_bytes == b"my-photo-bytes"
        assert content_type == "image/jpeg"

    async def test_raises_when_user_has_no_avatar(self, uow):
        user = await _make_saved_user(uow)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider())

        with pytest.raises(AvatarNotFoundError):
            await use_case.execute(str(user.id.value))

    async def test_raises_when_user_not_found(self, uow):
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider())

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value))


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


async def _bloqueo(social_uow, quien: User, a_quien: User) -> None:
    async with social_uow:
        await social_uow.friendships.add(
            Friendship.create_blocked(
                id=FriendshipId.generate(), blocker_id=quien.id, blocked_id=a_quien.id
            )
        )


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
        social_uow = InMemorySocialUnitOfWork()
        return dueno, yo, social_uow

    async def test_g2_si_el_me_bloqueo_no_veo_su_avatar(self, uow):
        """
        Given: El dueño del avatar me bloqueó
        When: Pido su avatar
        Then: UserNotFoundError, como una cuenta que no existe
        """
        dueno, yo, social_uow = await self._escena(uow)
        await _bloqueo(social_uow, dueno, yo)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), social_uow)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

    async def test_g2_si_lo_bloquee_yo_veo_su_avatar(self, uow):
        """
        Given: Bloqueé al dueño del avatar
        When: Pido su avatar
        Then: Lo veo: su perfil me enseña nombre, foto y «Desbloquear»
        """
        dueno, yo, social_uow = await self._escena(uow)
        await _bloqueo(social_uow, yo, dueno)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), social_uow)

        image_bytes, _ = await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

        assert image_bytes == b"preset-3-bytes"

    async def test_g2_sin_bloqueo_veo_su_avatar(self, uow):
        """
        Given: Ningún bloqueo entre los dos
        When: Pido su avatar
        Then: Lo veo
        """
        dueno, yo, social_uow = await self._escena(uow)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), social_uow)

        image_bytes, _ = await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))

        assert image_bytes == b"preset-3-bytes"

    async def test_g3_el_de_una_cuenta_desactivada_no_existe(self, uow):
        """
        Given: La cuenta del dueño está desactivada
        When: Pido su avatar
        Then: UserNotFoundError
        """
        dueno, yo, social_uow = await self._escena(uow)
        dueno.deactivate(deactivated_by_user_id=str(yo.id.value))
        await uow.users.save(dueno)
        use_case = GetAvatarImageUseCase(uow, FakeAvatarPresetProvider(), social_uow)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(dueno.id.value), viewer_id=str(yo.id.value))
