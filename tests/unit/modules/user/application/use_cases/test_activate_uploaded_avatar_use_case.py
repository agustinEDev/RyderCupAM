"""
Tests para ActivateUploadedAvatarUseCase.
"""

import pytest

from src.modules.user.application.use_cases.activate_uploaded_avatar_use_case import (
    ActivateUploadedAvatarUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import AvatarUploadNotFoundError, UserNotFoundError
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


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
class TestActivateUploadedAvatarUseCase:
    async def test_activates_own_previous_upload(self, uow):
        user = await _make_saved_user(uow)
        upload = UserAvatarUpload.create(user_id=user.id, image_data=b"jpeg-bytes")
        await uow.avatar_uploads.save(upload)
        use_case = ActivateUploadedAvatarUseCase(uow)

        response = await use_case.execute(str(user.id.value), str(upload.id.value))

        assert response.avatar_source == AvatarSource.UPLOAD
        stored_user = await uow.users.find_by_id(user.id)
        assert stored_user.active_avatar_upload_id == upload.id

    async def test_raises_when_user_not_found(self, uow):
        use_case = ActivateUploadedAvatarUseCase(uow)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(
                str(UserId.generate().value), str(UserAvatarUploadId.generate().value)
            )

    async def test_raises_when_upload_does_not_exist(self, uow):
        user = await _make_saved_user(uow)
        use_case = ActivateUploadedAvatarUseCase(uow)

        with pytest.raises(AvatarUploadNotFoundError):
            await use_case.execute(str(user.id.value), str(UserAvatarUploadId.generate().value))

    async def test_raises_when_upload_belongs_to_another_user(self, uow):
        user = await _make_saved_user(uow)
        other_user = await _make_saved_user(uow)
        upload = UserAvatarUpload.create(user_id=other_user.id, image_data=b"jpeg-bytes")
        await uow.avatar_uploads.save(upload)
        use_case = ActivateUploadedAvatarUseCase(uow)

        with pytest.raises(AvatarUploadNotFoundError):
            await use_case.execute(str(user.id.value), str(upload.id.value))
