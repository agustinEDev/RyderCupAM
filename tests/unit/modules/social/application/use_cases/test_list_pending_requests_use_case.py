"""Tests para ListPendingRequestsUseCase."""

import pytest

from src.modules.social.application.use_cases.list_pending_requests_use_case import (
    ListPendingRequestsUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)

pytestmark = pytest.mark.asyncio


class TestListPendingRequestsUseCase:
    @pytest.fixture
    def uow(self):
        return InMemorySocialUnitOfWork()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(self, user_uow, email):
        user = User.create(
            first_name="Test",
            last_name="User",
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def test_lists_received_requests(self, uow, user_uow):
        me = await self._create_user(user_uow, "me@test.com")
        other = await self._create_user(user_uow, "other@test.com")

        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=other.id, addressee_id=me.id
        )
        async with uow:
            await uow.friendships.add(friendship)

        use_case = ListPendingRequestsUseCase(uow, user_uow)
        result = await use_case.execute(str(me.id.value), direction="received")

        assert result.total_count == 1
        assert result.friendships[0].requester_id == other.id.value

    async def test_lists_sent_requests(self, uow, user_uow):
        me = await self._create_user(user_uow, "me2@test.com")
        other = await self._create_user(user_uow, "other2@test.com")

        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=me.id, addressee_id=other.id
        )
        async with uow:
            await uow.friendships.add(friendship)

        use_case = ListPendingRequestsUseCase(uow, user_uow)
        result = await use_case.execute(str(me.id.value), direction="sent")

        assert result.total_count == 1
        assert result.friendships[0].addressee_id == other.id.value

    async def test_invalid_direction_raises(self, uow, user_uow):
        from uuid import uuid4

        use_case = ListPendingRequestsUseCase(uow, user_uow)
        with pytest.raises(ValueError, match="Invalid direction"):
            await use_case.execute(str(uuid4()), direction="sideways")
