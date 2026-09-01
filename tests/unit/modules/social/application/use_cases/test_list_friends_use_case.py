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


class TestListFriendsShowsTheAlias:
    """
    La lista de amigos pinta el alias de quien lo tenga (BE #239).

    Es de las pantallas donde más se lee un nombre, y el `display_name` del
    backend es lo único que decide cuál se ve.
    """

    @pytest.fixture
    def uow(self):
        return InMemorySocialUnitOfWork()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _create_user(self, user_uow, email, first_name="Test", alias=None):
        user = User.create(
            first_name=first_name,
            last_name="User",
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        if alias:
            user.update_profile(alias=alias)
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def test_a_friend_with_an_alias_is_listed_by_it(self, uow, user_uow):
        me = await self._create_user(user_uow, "yo@test.com", first_name="Agustin")
        friend = await self._create_user(
            user_uow, "chuchi@test.com", first_name="Jose", alias="Chuchi"
        )
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=me.id, addressee_id=friend.id
        )
        friendship.accept()
        async with uow:
            await uow.friendships.add(friendship)

        result = await ListFriendsUseCase(uow, user_uow).execute(str(me.id.value))

        assert result.friendships[0].addressee_name == "Chuchi"
        assert result.friendships[0].requester_name == "Agustin User"

    async def test_a_friend_without_an_alias_keeps_their_name(self, uow, user_uow):
        me = await self._create_user(user_uow, "yo2@test.com", first_name="Agustin")
        friend = await self._create_user(user_uow, "ana@test.com", first_name="Ana")
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=me.id, addressee_id=friend.id
        )
        friendship.accept()
        async with uow:
            await uow.friendships.add(friendship)

        result = await ListFriendsUseCase(uow, user_uow).execute(str(me.id.value))

        assert result.friendships[0].addressee_name == "Ana User"
