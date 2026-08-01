"""Tests para AdminListUsersUseCase."""

import pytest

from src.modules.user.application.dto.admin_dto import AdminListUsersRequestDTO
from src.modules.user.application.use_cases.admin_list_users_use_case import (
    AdminListUsersUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)

pytestmark = pytest.mark.asyncio


class TestAdminListUsersUseCase:
    @pytest.fixture
    def uow(self):
        return InMemoryUnitOfWork()

    async def _create_user(self, uow, first_name, last_name, email):
        user = User.create(
            first_name=first_name,
            last_name=last_name,
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        async with uow:
            await uow.users.save(user)
        return user

    async def test_lists_all_users_paginated(self, uow):
        await self._create_user(uow, "Ana", "Ruiz", "ana@test.com")
        await self._create_user(uow, "Bea", "Soto", "bea@test.com")

        use_case = AdminListUsersUseCase(uow)
        response = await use_case.execute(AdminListUsersRequestDTO(limit=1, offset=0))

        assert response.total_count == 2
        assert len(response.users) == 1

    async def test_search_filters_by_name_or_email(self, uow):
        await self._create_user(uow, "Marta", "Sánchez", "marta@test.com")
        await self._create_user(uow, "Diego", "Molero", "diego@test.com")

        use_case = AdminListUsersUseCase(uow)
        response = await use_case.execute(AdminListUsersRequestDTO(search="marta"))

        assert response.total_count == 1
        assert response.users[0].email == "marta@test.com"

    async def test_search_matches_email_too(self, uow):
        await self._create_user(uow, "Marta", "Sánchez", "findme@test.com")

        use_case = AdminListUsersUseCase(uow)
        response = await use_case.execute(AdminListUsersRequestDTO(search="findme"))

        assert response.total_count == 1

    async def test_filters_by_is_admin(self, uow):
        admin = await self._create_user(uow, "Admin", "User", "admin@test.com")
        async with uow:
            admin.set_is_admin(True)
            await uow.users.save(admin)
        await self._create_user(uow, "Player", "User", "player@test.com")

        use_case = AdminListUsersUseCase(uow)
        response = await use_case.execute(AdminListUsersRequestDTO(is_admin=True))

        assert response.total_count == 1
        assert response.users[0].email == "admin@test.com"

    async def test_filters_by_is_active(self, uow):
        user = await self._create_user(uow, "Deactivated", "User", "gone@test.com")
        async with uow:
            user.deactivate(deactivated_by_user_id="admin-id")
            await uow.users.save(user)
        await self._create_user(uow, "Active", "User", "active@test.com")

        use_case = AdminListUsersUseCase(uow)
        response = await use_case.execute(AdminListUsersRequestDTO(is_active=False))

        assert response.total_count == 1
        assert response.users[0].email == "gone@test.com"

    async def test_filters_by_email_verified(self, uow):
        await self._create_user(uow, "Unverified", "User", "unverified@test.com")
        verified = await self._create_user(uow, "Verified", "User", "verified@test.com")
        async with uow:
            verified.verify_email_from_oauth()
            await uow.users.save(verified)

        use_case = AdminListUsersUseCase(uow)
        response = await use_case.execute(AdminListUsersRequestDTO(email_verified=False))

        assert response.total_count == 1
        assert response.users[0].email == "unverified@test.com"
