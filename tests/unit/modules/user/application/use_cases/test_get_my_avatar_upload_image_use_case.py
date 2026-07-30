"""
Tests para GetMyAvatarUploadImageUseCase.
"""

import pytest

from src.modules.user.application.use_cases.get_my_avatar_upload_image_use_case import (
    GetMyAvatarUploadImageUseCase,
)
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import AvatarUploadNotFoundError
from src.modules.user.domain.value_objects.user_avatar_upload_id import UserAvatarUploadId
from src.modules.user.domain.value_objects.user_id import UserId
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.mark.asyncio
class TestGetMyAvatarUploadImageUseCase:
    async def test_returns_bytes_for_own_upload(self, uow):
        user_id = UserId.generate()
        upload = UserAvatarUpload.create(user_id=user_id, image_data=b"photo-bytes")
        await uow.avatar_uploads.save(upload)
        use_case = GetMyAvatarUploadImageUseCase(uow)

        image_bytes, content_type = await use_case.execute(
            str(user_id.value), str(upload.id.value)
        )

        assert image_bytes == b"photo-bytes"
        assert content_type == "image/jpeg"

    async def test_raises_when_upload_does_not_exist(self, uow):
        use_case = GetMyAvatarUploadImageUseCase(uow)

        with pytest.raises(AvatarUploadNotFoundError):
            await use_case.execute(
                str(UserId.generate().value), str(UserAvatarUploadId.generate().value)
            )

    async def test_raises_when_upload_belongs_to_another_user(self, uow):
        owner_id = UserId.generate()
        other_user_id = UserId.generate()
        upload = UserAvatarUpload.create(user_id=owner_id, image_data=b"photo-bytes")
        await uow.avatar_uploads.save(upload)
        use_case = GetMyAvatarUploadImageUseCase(uow)

        with pytest.raises(AvatarUploadNotFoundError):
            await use_case.execute(str(other_user_id.value), str(upload.id.value))
