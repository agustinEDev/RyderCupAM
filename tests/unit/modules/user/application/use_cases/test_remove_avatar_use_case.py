"""
Tests para RemoveAvatarUseCase.
"""

import pytest

from src.modules.user.application.use_cases.remove_avatar_use_case import RemoveAvatarUseCase
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.domain.value_objects.avatar_source import AvatarSource
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
class TestRemoveAvatarUseCase:
    async def test_clears_active_avatar(self, uow):
        user = await _make_saved_user(uow)
        user.set_preset_avatar(2)
        await uow.users.save(user)
        use_case = RemoveAvatarUseCase(uow)

        response = await use_case.execute(str(user.id.value))

        assert response.avatar_source == AvatarSource.NONE
        assert response.avatar_preset_id is None

    async def test_raises_when_user_not_found(self, uow):
        use_case = RemoveAvatarUseCase(uow)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value))
