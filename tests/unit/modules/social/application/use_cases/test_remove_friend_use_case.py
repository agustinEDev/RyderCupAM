"""Tests para RemoveFriendUseCase."""

from uuid import uuid4

import pytest

from src.modules.social.application.exceptions import (
    FriendshipNotFoundError,
    NotFriendshipParticipantError,
)
from src.modules.social.application.use_cases.remove_friend_use_case import RemoveFriendUseCase
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


class TestRemoveFriendUseCase:
    @pytest.fixture
    def uow(self):
        return InMemorySocialUnitOfWork()

    async def _add(self, uow, friendship):
        async with uow:
            await uow.friendships.add(friendship)
        return friendship

    async def test_not_found_raises(self, uow):
        use_case = RemoveFriendUseCase(uow)
        with pytest.raises(FriendshipNotFoundError):
            await use_case.execute(str(uuid4()), str(uuid4()))

    async def test_requester_can_cancel_pending(self, uow):
        requester = UserId(uuid4())
        addressee = UserId(uuid4())
        friendship = await self._add(
            uow, Friendship.create(id=FriendshipId.generate(), requester_id=requester, addressee_id=addressee)
        )

        use_case = RemoveFriendUseCase(uow)
        await use_case.execute(str(friendship.id.value), str(requester.value))

        async with uow:
            assert await uow.friendships.find_by_id(friendship.id) is None

    async def test_addressee_cannot_cancel_pending(self, uow):
        requester = UserId(uuid4())
        addressee = UserId(uuid4())
        friendship = await self._add(
            uow, Friendship.create(id=FriendshipId.generate(), requester_id=requester, addressee_id=addressee)
        )

        use_case = RemoveFriendUseCase(uow)
        with pytest.raises(NotFriendshipParticipantError):
            await use_case.execute(str(friendship.id.value), str(addressee.value))

    async def test_either_participant_can_remove_accepted(self, uow):
        requester = UserId(uuid4())
        addressee = UserId(uuid4())
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=requester, addressee_id=addressee
        )
        friendship.accept()
        await self._add(uow, friendship)

        use_case = RemoveFriendUseCase(uow)
        await use_case.execute(str(friendship.id.value), str(addressee.value))

        async with uow:
            assert await uow.friendships.find_by_id(friendship.id) is None

    async def test_third_party_cannot_remove_accepted(self, uow):
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=UserId(uuid4()), addressee_id=UserId(uuid4())
        )
        friendship.accept()
        await self._add(uow, friendship)

        use_case = RemoveFriendUseCase(uow)
        with pytest.raises(NotFriendshipParticipantError):
            await use_case.execute(str(friendship.id.value), str(uuid4()))

    async def test_only_blocker_can_unblock(self, uow):
        blocker = UserId(uuid4())
        blocked = UserId(uuid4())
        friendship = Friendship.create_blocked(
            id=FriendshipId.generate(), blocker_id=blocker, blocked_id=blocked
        )
        await self._add(uow, friendship)

        use_case = RemoveFriendUseCase(uow)
        with pytest.raises(NotFriendshipParticipantError):
            await use_case.execute(str(friendship.id.value), str(blocked.value))

        await use_case.execute(str(friendship.id.value), str(blocker.value))

        async with uow:
            assert await uow.friendships.find_by_id(friendship.id) is None
