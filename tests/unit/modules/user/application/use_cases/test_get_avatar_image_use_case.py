"""
Tests para GetAvatarImageUseCase.

Usa un IAvatarPresetProvider falso para no depender de los assets reales en disco.
"""

import pytest

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
