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


class TestListFriendsCarriesTheHandicap:
    """
    El resumen del asistente de partida rápida enseña el hándicap de cada amigo
    antes de crear nada (FE #848): la lista lo trae, y nulo si no lo tiene.
    Los usuarios se leen en una sola consulta, no uno a uno.
    """

    @pytest.fixture
    def uow(self):
        return InMemorySocialUnitOfWork()

    @pytest.fixture
    def user_uow(self):
        return UserInMemoryUoW()

    async def _user(self, user_uow, email, handicap=None):
        user = User.create(
            first_name="Test",
            last_name="User",
            email_str=email,
            plain_password="SecureP@ssw0rd123",
        )
        if handicap is not None:
            user.update_handicap(handicap)
        async with user_uow:
            await user_uow.users.save(user)
        return user

    async def _friends(self, uow, a, b):
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=a.id, addressee_id=b.id
        )
        friendship.accept()
        async with uow:
            await uow.friendships.add(friendship)

    async def test_list_friends_with_handicaps_returns_both_sides(self, uow, user_uow):
        """Given two friends with handicap, when listing, then each side carries its own."""
        me = await self._user(user_uow, "me_hcp@test.com", handicap=12.4)
        friend = await self._user(user_uow, "friend_hcp@test.com", handicap=20.1)
        await self._friends(uow, me, friend)

        (item,) = (await ListFriendsUseCase(uow, user_uow).execute(str(me.id.value))).friendships

        assert item.requester_handicap == 12.4
        assert item.addressee_handicap == 20.1

    async def test_list_friends_without_handicap_returns_none(self, uow, user_uow):
        """Given a friend without handicap, when listing, then it is None, not 0."""
        me = await self._user(user_uow, "me_nohcp@test.com", handicap=5.0)
        friend = await self._user(user_uow, "friend_nohcp@test.com")
        await self._friends(uow, friend, me)

        (item,) = (await ListFriendsUseCase(uow, user_uow).execute(str(me.id.value))).friendships

        assert item.requester_handicap is None
        assert item.addressee_handicap == 5.0

    async def test_list_friends_reads_users_in_one_query(self, uow, user_uow):
        """Given several friends, when listing, then users are read once, not one by one."""
        me = await self._user(user_uow, "me_n1@test.com")
        for i in range(3):
            await self._friends(uow, me, await self._user(user_uow, f"f{i}_n1@test.com"))
        llamadas = []
        original = user_uow.users.find_by_id

        async def cuenta(user_id):
            llamadas.append(user_id)
            return await original(user_id)

        user_uow.users.find_by_id = cuenta

        result = await ListFriendsUseCase(uow, user_uow).execute(str(me.id.value))

        assert len(result.friendships) == 3
        assert llamadas == []
