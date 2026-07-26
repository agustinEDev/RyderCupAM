"""Tests para SendFriendRequestUseCase."""

import pytest

from src.modules.social.application.dto.friendship_dto import SendFriendRequestRequestDTO
from src.modules.social.application.exceptions import AddresseeNotFoundError
from src.modules.social.application.use_cases.send_friend_request_use_case import (
    SendFriendRequestUseCase,
)
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.exceptions.social_violations import (
    BlockedUserViolation,
    DuplicateFriendRequestViolation,
    SelfFriendRequestViolation,
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


class TestSendFriendRequestUseCase:
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

    async def test_send_request_success(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester@test.com")
        addressee = await self._create_user(user_uow, "addressee@test.com")

        use_case = SendFriendRequestUseCase(uow, user_uow)
        response = await use_case.execute(
            SendFriendRequestRequestDTO(
                requester_id=requester.id.value, addressee_id=addressee.id.value
            )
        )

        assert response.status == "PENDING"
        assert response.requester_id == requester.id.value
        assert response.addressee_id == addressee.id.value

    async def test_self_request_raises(self, uow, user_uow):
        user = await self._create_user(user_uow, "solo@test.com")
        use_case = SendFriendRequestUseCase(uow, user_uow)

        with pytest.raises(SelfFriendRequestViolation):
            await use_case.execute(
                SendFriendRequestRequestDTO(requester_id=user.id.value, addressee_id=user.id.value)
            )

    async def test_addressee_not_found_raises(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester2@test.com")
        use_case = SendFriendRequestUseCase(uow, user_uow)

        from uuid import uuid4

        with pytest.raises(AddresseeNotFoundError):
            await use_case.execute(
                SendFriendRequestRequestDTO(requester_id=requester.id.value, addressee_id=uuid4())
            )

    async def test_duplicate_pending_request_raises(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester3@test.com")
        addressee = await self._create_user(user_uow, "addressee3@test.com")
        use_case = SendFriendRequestUseCase(uow, user_uow)
        dto = SendFriendRequestRequestDTO(
            requester_id=requester.id.value, addressee_id=addressee.id.value
        )

        await use_case.execute(dto)

        with pytest.raises(DuplicateFriendRequestViolation):
            await use_case.execute(dto)

    async def test_blocked_relationship_raises(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester4@test.com")
        addressee = await self._create_user(user_uow, "addressee4@test.com")

        blocked = Friendship.create_blocked(
            id=FriendshipId.generate(),
            blocker_id=addressee.id,
            blocked_id=requester.id,
        )
        async with uow:
            await uow.friendships.add(blocked)

        use_case = SendFriendRequestUseCase(uow, user_uow)
        with pytest.raises(BlockedUserViolation):
            await use_case.execute(
                SendFriendRequestRequestDTO(
                    requester_id=requester.id.value, addressee_id=addressee.id.value
                )
            )

    async def test_resend_after_declined_creates_new_pending(self, uow, user_uow):
        requester = await self._create_user(user_uow, "requester5@test.com")
        addressee = await self._create_user(user_uow, "addressee5@test.com")

        declined = Friendship.create(
            id=FriendshipId.generate(), requester_id=requester.id, addressee_id=addressee.id
        )
        declined.decline()
        async with uow:
            await uow.friendships.add(declined)

        use_case = SendFriendRequestUseCase(uow, user_uow)
        response = await use_case.execute(
            SendFriendRequestRequestDTO(
                requester_id=requester.id.value, addressee_id=addressee.id.value
            )
        )

        assert response.status == "PENDING"
        assert response.id != declined.id.value
