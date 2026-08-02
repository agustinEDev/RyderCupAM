"""Tests para AdminUpdateUserUseCase."""

import pytest

from src.modules.user.application.dto.admin_dto import AdminUpdateUserRequestDTO
from src.modules.user.application.use_cases.admin_update_user_use_case import (
    AdminUpdateUserUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import DuplicateEmailError, UserNotFoundError
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


class TestAdminUpdateUserUseCase:
    @pytest.fixture
    def uow(self):
        return InMemoryUnitOfWork()

    @pytest.fixture
    async def existing_user(self, uow):
        user = User.create(
            first_name="Carlos",
            last_name="Ruiz",
            email_str="carlos@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with uow:
            await uow.users.save(user)
        return user

    async def test_updates_name_and_handicap(self, uow, existing_user):
        use_case = AdminUpdateUserUseCase(uow)
        result = await use_case.execute(
            str(existing_user.id.value),
            AdminUpdateUserRequestDTO(first_name="Carlitos", handicap=12.5),
        )

        assert result.first_name == "Carlitos"
        assert result.handicap == 12.5

    async def test_promotes_user_to_admin(self, uow, existing_user):
        use_case = AdminUpdateUserUseCase(uow)
        result = await use_case.execute(
            str(existing_user.id.value), AdminUpdateUserRequestDTO(is_admin=True)
        )

        assert result.is_admin is True

    async def test_changes_email(self, uow, existing_user):
        use_case = AdminUpdateUserUseCase(uow)
        result = await use_case.execute(
            str(existing_user.id.value),
            AdminUpdateUserRequestDTO(email="new-email@test.com"),
        )

        assert result.email == "new-email@test.com"

    async def test_raises_when_user_not_found(self, uow):
        from uuid import uuid4

        use_case = AdminUpdateUserUseCase(uow)
        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(uuid4()), AdminUpdateUserRequestDTO(first_name="X"))

    async def test_raises_on_duplicate_email(self, uow, existing_user):
        other = User.create(
            first_name="Otro",
            last_name="Usuario",
            email_str="taken@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with uow:
            await uow.users.save(other)

        use_case = AdminUpdateUserUseCase(uow)
        with pytest.raises(DuplicateEmailError):
            await use_case.execute(
                str(existing_user.id.value),
                AdminUpdateUserRequestDTO(email="taken@test.com"),
            )
