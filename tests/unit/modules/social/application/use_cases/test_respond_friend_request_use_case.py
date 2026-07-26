"""Tests para RespondFriendRequestUseCase."""

from uuid import uuid4

import pytest

from src.modules.social.application.dto.friendship_dto import RespondFriendRequestRequestDTO
from src.modules.social.application.exceptions import FriendshipNotFoundError, NotAddresseeError
from src.modules.social.application.use_cases.respond_friend_request_use_case import (
    RespondFriendRequestUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    InvalidFriendshipStatusViolation,
)
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)

pytestmark = pytest.mark.asyncio


class TestRespondFriendRequestUseCase:
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

    async def _create_pending(self, uow, requester_id, addressee_id):
        friendship = Friendship.create(
            id=FriendshipId.generate(), requester_id=requester_id, addressee_id=addressee_id
        )
        async with uow:
            await uow.friendships.add(friendship)
        return friendship

    async def test_accept_success(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester@test.com")
        addressee = await self._create_user(user_uow, "addressee@test.com")
        friendship = await self._create_pending(uow, requester.id, addressee.id)

        use_case = RespondFriendRequestUseCase(uow, user_uow)
        response = await use_case.execute(
            RespondFriendRequestRequestDTO(
                friendship_id=friendship.id.value, user_id=addressee.id.value, action="ACCEPT"
            )
        )

        assert response.status == "ACCEPTED"

    async def test_decline_success(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester2@test.com")
        addressee = await self._create_user(user_uow, "addressee2@test.com")
        friendship = await self._create_pending(uow, requester.id, addressee.id)

        use_case = RespondFriendRequestUseCase(uow, user_uow)
        response = await use_case.execute(
            RespondFriendRequestRequestDTO(
                friendship_id=friendship.id.value, user_id=addressee.id.value, action="DECLINE"
            )
        )

        assert response.status == "DECLINED"

    async def test_not_found_raises(self, uow, user_uow):
        use_case = RespondFriendRequestUseCase(uow, user_uow)
        with pytest.raises(FriendshipNotFoundError):
            await use_case.execute(
                RespondFriendRequestRequestDTO(
                    friendship_id=uuid4(), user_id=uuid4(), action="ACCEPT"
                )
            )

    async def test_non_addressee_raises(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester3@test.com")
        addressee = await self._create_user(user_uow, "addressee3@test.com")
        friendship = await self._create_pending(uow, requester.id, addressee.id)

        use_case = RespondFriendRequestUseCase(uow, user_uow)
        with pytest.raises(NotAddresseeError):
            await use_case.execute(
                RespondFriendRequestRequestDTO(
                    friendship_id=friendship.id.value,
                    user_id=requester.id.value,
                    action="ACCEPT",
                )
            )

    async def test_already_responded_raises(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester4@test.com")
        addressee = await self._create_user(user_uow, "addressee4@test.com")
        friendship = await self._create_pending(uow, requester.id, addressee.id)

        use_case = RespondFriendRequestUseCase(uow, user_uow)
        dto = RespondFriendRequestRequestDTO(
            friendship_id=friendship.id.value, user_id=addressee.id.value, action="ACCEPT"
        )
        await use_case.execute(dto)

        with pytest.raises(InvalidFriendshipStatusViolation):
            await use_case.execute(dto)
