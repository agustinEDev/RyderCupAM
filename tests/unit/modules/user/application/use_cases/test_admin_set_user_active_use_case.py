"""Tests para AdminSetUserActiveUseCase."""

import pytest

from src.modules.user.application.use_cases.admin_set_user_active_use_case import (
    AdminSetUserActiveUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.domain.errors.user_errors import UserNotFoundError
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


class TestAdminSetUserActiveUseCase:
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

    async def test_deactivates_active_user(self, uow, existing_user):
        use_case = AdminSetUserActiveUseCase(uow)
        await use_case.execute(str(existing_user.id.value), False, actor_user_id="admin-id")

        async with uow:
            user = await uow.users.find_by_id(existing_user.id)
        assert user.is_active is False

    async def test_reactivates_deactivated_user(self, uow, existing_user):
        use_case = AdminSetUserActiveUseCase(uow)
        await use_case.execute(str(existing_user.id.value), False, actor_user_id="admin-id")
        await use_case.execute(str(existing_user.id.value), True, actor_user_id="admin-id")

        async with uow:
            user = await uow.users.find_by_id(existing_user.id)
        assert user.is_active is True

    async def test_is_idempotent_when_already_in_target_state(self, uow, existing_user):
        use_case = AdminSetUserActiveUseCase(uow)
        # Ya está activo por defecto: no debe lanzar al pedir is_active=True
        await use_case.execute(str(existing_user.id.value), True, actor_user_id="admin-id")

        async with uow:
            user = await uow.users.find_by_id(existing_user.id)
        assert user.is_active is True

    async def test_raises_when_user_not_found(self, uow):
        from uuid import uuid4

        use_case = AdminSetUserActiveUseCase(uow)
        with pytest.raises(UserNotFoundError):
            await use_case.execute(str(uuid4()), False, actor_user_id="admin-id")
