"""Tests para ListFriendsUseCase."""

import pytest

from src.modules.social.application.use_cases.list_friends_use_case import ListFriendsUseCase
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


class TestListFriendsUseCase:
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

    async def test_lists_only_accepted_friendships(self, uow, user_uow):
        me = await self._create_user(user_uow, "me@test.com")
        friend = await self._create_user(user_uow, "friend@test.com")
        pending_user = await self._create_user(user_uow, "pending@test.com")

        accepted = Friendship.create(
            id=FriendshipId.generate(), requester_id=me.id, addressee_id=friend.id
        )
        accepted.accept()
        pending = Friendship.create(
            id=FriendshipId.generate(), requester_id=me.id, addressee_id=pending_user.id
        )
        async with uow:
            await uow.friendships.add(accepted)
            await uow.friendships.add(pending)

        use_case = ListFriendsUseCase(uow, user_uow)
        result = await use_case.execute(str(me.id.value))

        assert result.total_count == 1
        assert len(result.friendships) == 1
        assert result.friendships[0].status == "ACCEPTED"

    async def test_empty_when_no_friends(self, uow, user_uow):
        me = await self._create_user(user_uow, "lonely@test.com")
        use_case = ListFriendsUseCase(uow, user_uow)

        result = await use_case.execute(str(me.id.value))

        assert result.total_count == 0
        assert result.friendships == []
