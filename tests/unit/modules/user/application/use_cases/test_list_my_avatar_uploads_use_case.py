"""
Tests para ListMyAvatarUploadsUseCase.
"""

import pytest

from src.modules.user.application.use_cases.list_my_avatar_uploads_use_case import (
    ListMyAvatarUploadsUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.entities.user_avatar_upload import UserAvatarUpload
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.value_objects.email import Email
from src.modules.user.domain.value_objects.password import Password
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
class TestListMyAvatarUploadsUseCase:
    async def test_lists_uploads_marking_active_one(self, uow):
        user = await _make_saved_user(uow)
        upload1 = UserAvatarUpload.create(user_id=user.id, image_data=b"one")
        upload2 = UserAvatarUpload.create(user_id=user.id, image_data=b"two")
        await uow.avatar_uploads.save(upload1)
        await uow.avatar_uploads.save(upload2)
        user.set_uploaded_avatar(upload2.id)
        await uow.users.save(user)
        use_case = ListMyAvatarUploadsUseCase(uow)

        results = await use_case.execute(str(user.id.value))

        assert len(results) == 2
        active_flags = {str(r.id): r.is_active for r in results}
        assert active_flags[str(upload2.id.value)] is True
        assert active_flags[str(upload1.id.value)] is False

    async def test_returns_empty_list_when_no_uploads(self, uow):
        user = await _make_saved_user(uow)
        use_case = ListMyAvatarUploadsUseCase(uow)

        results = await use_case.execute(str(user.id.value))

        assert results == []

    async def test_raises_when_user_not_found(self, uow):
        use_case = ListMyAvatarUploadsUseCase(uow)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value))
