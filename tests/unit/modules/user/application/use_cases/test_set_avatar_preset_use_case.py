"""
Tests para SetAvatarPresetUseCase.
"""

import pytest
from pydantic import ValidationError

from src.modules.user.application.dto.avatar_dto import SetAvatarPresetRequestDTO
from src.modules.user.application.use_cases.set_avatar_preset_use_case import (
    SetAvatarPresetUseCase,
)
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
class TestSetAvatarPresetUseCase:
    async def test_activates_preset_for_existing_user(self, uow):
        user = await _make_saved_user(uow)
        use_case = SetAvatarPresetUseCase(uow)

        response = await use_case.execute(
            str(user.id.value), SetAvatarPresetRequestDTO(preset_id=4)
        )

        assert response.avatar_source == AvatarSource.PRESET
        assert response.avatar_preset_id == 4
        stored_user = await uow.users.find_by_id(user.id)
        assert stored_user.avatar_preset_id == 4

    async def test_raises_when_user_not_found(self, uow):
        use_case = SetAvatarPresetUseCase(uow)

        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(UserId.generate().value), SetAvatarPresetRequestDTO(preset_id=1))

    async def test_dto_rejects_preset_id_out_of_range(self):
        with pytest.raises(ValidationError):
            SetAvatarPresetRequestDTO(preset_id=99)
