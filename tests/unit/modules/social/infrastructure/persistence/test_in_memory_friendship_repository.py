"""Tests para InMemoryFriendshipRepository."""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_friendship_repository import (
    InMemoryFriendshipRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class TestInMemoryFriendshipRepository:
    @pytest.fixture
    def repo(self):
        return InMemoryFriendshipRepository()

    async def test_add_and_find_by_id(self, repo):
        friendship = Friendship.create(
            id=FriendshipId.generate(),
            requester_id=UserId(uuid4()),
            addressee_id=UserId(uuid4()),
        )
        await repo.add(friendship)

        found = await repo.find_by_id(friendship.id)
        assert found == friendship

    async def test_find_by_id_not_found_returns_none(self, repo):
        assert await repo.find_by_id(FriendshipId.generate()) is None

    async def test_find_by_pair_matches_either_direction(self, repo):
        a = UserId(uuid4())
        b = UserId(uuid4())
        friendship = Friendship.create(id=FriendshipId.generate(), requester_id=a, addressee_id=b)
        await repo.add(friendship)

        assert await repo.find_by_pair(a, b) == friendship
        assert await repo.find_by_pair(b, a) == friendship

    async def test_remove_deletes_friendship(self, repo):
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=UserId(uuid4()), addressee_id=UserId(uuid4())
        )
        await repo.add(friendship)
        await repo.remove(friendship)

        assert await repo.find_by_id(friendship.id) is None

    async def test_list_friends_only_accepted(self, repo):
        user = UserId(uuid4())
        accepted = Friendship.create(
            id=FriendshipId.generate(), requester_id=user, addressee_id=UserId(uuid4())
        )
        accepted.accept()
        pending = Friendship.create(
            id=FriendshipId.generate(), requester_id=user, addressee_id=UserId(uuid4())
        )
        await repo.add(accepted)
        await repo.add(pending)

        friends = await repo.list_friends(user)
        assert friends == [accepted]

    async def test_list_pending_received(self, repo):
        addressee = UserId(uuid4())
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=UserId(uuid4()), addressee_id=addressee
        )
        await repo.add(friendship)

        received = await repo.list_pending_received(addressee)
        assert received == [friendship]
        assert await repo.list_pending_sent(addressee) == []

    async def test_list_pending_sent(self, repo):
        requester = UserId(uuid4())
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=requester, addressee_id=UserId(uuid4())
        )
        await repo.add(friendship)

        sent = await repo.list_pending_sent(requester)
        assert sent == [friendship]

    async def test_counts(self, repo):
        user = UserId(uuid4())
        accepted = Friendship.create(
            id=FriendshipId.generate(), requester_id=user, addressee_id=UserId(uuid4())
        )
        accepted.accept()
        received = Friendship.create(
            id=FriendshipId.generate(), requester_id=UserId(uuid4()), addressee_id=user
        )
        sent = Friendship.create(
            id=FriendshipId.generate(), requester_id=user, addressee_id=UserId(uuid4())
        )
        await repo.add(accepted)
        await repo.add(received)
        await repo.add(sent)

        assert await repo.count_friends(user) == 1
        assert await repo.count_pending_received(user) == 1
        assert await repo.count_pending_sent(user) == 1

    async def test_are_friends(self, repo):
        a = UserId(uuid4())
        b = UserId(uuid4())
        friendship = Friendship.create(id=FriendshipId.generate(), requester_id=a, addressee_id=b)
        await repo.add(friendship)

        assert not await repo.are_friends(a, b)

        friendship.accept()
        await repo.update(friendship)

        assert await repo.are_friends(a, b)
        assert await repo.are_friends(b, a)
