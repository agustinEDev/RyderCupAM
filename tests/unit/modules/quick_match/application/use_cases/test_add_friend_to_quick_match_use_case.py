"""Tests para AddFriendToQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.quick_match.application.dto.quick_match_dto import AddParticipantRequestDTO
from src.modules.quick_match.application.exceptions import (
    FriendUserNotFoundError,
    InvalidTeeSelectionError,
    NotFriendsError,
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.add_friend_to_quick_match_use_case import (
    AddFriendToQuickMatchUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from tests.unit.modules.quick_match.conftest import (
    create_accepted_friendship,
    create_golf_course,
    create_user,
)

pytestmark = pytest.mark.asyncio


async def _create_pending_match(qm_uow, golf_course_uow, creator):
    golf_course = await create_golf_course(golf_course_uow, creator.id)
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator.id,
        golf_course_id=golf_course.id,
        match_format=MatchFormat.SINGLES,
    )
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestAddFriendToQuickMatchUseCase:
    async def test_add_accepted_friend_succeeds(
        self, qm_uow, golf_course_uow, social_uow, user_uow
    ):
        creator = await create_user(user_uow, "creator@test.com")
        friend = await create_user(user_uow, "friend@test.com")
        await create_accepted_friendship(social_uow, creator.id, friend.id)
        qm = await _create_pending_match(qm_uow, golf_course_uow, creator)

        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        response = await use_case.execute(
            AddParticipantRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator.id.value,
                friend_user_id=friend.id.value,
            )
        )

        assert len(response.participants) == 2

    async def test_add_non_friend_raises(self, qm_uow, golf_course_uow, social_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        stranger = await create_user(user_uow, "stranger@test.com")
        qm = await _create_pending_match(qm_uow, golf_course_uow, creator)

        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        with pytest.raises(NotFriendsError):
            await use_case.execute(
                AddParticipantRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=creator.id.value,
                    friend_user_id=stranger.id.value,
                )
            )

    async def test_non_creator_cannot_add(self, qm_uow, golf_course_uow, social_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        other_participant = await create_user(user_uow, "other3@test.com")
        friend = await create_user(user_uow, "friend3@test.com")
        await create_accepted_friendship(social_uow, other_participant.id, friend.id)
        qm = await _create_pending_match(qm_uow, golf_course_uow, creator)

        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        with pytest.raises(NotQuickMatchCreatorError):
            await use_case.execute(
                AddParticipantRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=other_participant.id.value,
                    friend_user_id=friend.id.value,
                )
            )

    async def test_friend_user_not_found_raises(
        self, qm_uow, golf_course_uow, social_uow, user_uow
    ):
        creator = await create_user(user_uow, "creator4@test.com")
        qm = await _create_pending_match(qm_uow, golf_course_uow, creator)

        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        with pytest.raises(FriendUserNotFoundError):
            await use_case.execute(
                AddParticipantRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=creator.id.value,
                    friend_user_id=uuid4(),
                )
            )

    async def test_quick_match_not_found_raises(
        self, qm_uow, golf_course_uow, social_uow, user_uow
    ):
        creator = await create_user(user_uow, "creator5@test.com")
        friend = await create_user(user_uow, "friend5@test.com")
        await create_accepted_friendship(social_uow, creator.id, friend.id)

        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                AddParticipantRequestDTO(
                    quick_match_id=uuid4(),
                    requester_id=creator.id.value,
                    friend_user_id=friend.id.value,
                )
            )

    async def test_add_friend_with_valid_tee_succeeds(
        self, qm_uow, golf_course_uow, social_uow, user_uow
    ):
        creator = await create_user(user_uow, "creator6@test.com")
        friend = await create_user(user_uow, "friend6@test.com")
        await create_accepted_friendship(social_uow, creator.id, friend.id)
        qm = await _create_pending_match(qm_uow, golf_course_uow, creator)

        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        response = await use_case.execute(
            AddParticipantRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator.id.value,
                friend_user_id=friend.id.value,
                tee_category="AMATEUR",
                tee_gender="MALE",
            )
        )

        friend_dto = next(p for p in response.participants if p.user_id == friend.id.value)
        assert friend_dto.tee_category == "AMATEUR"
        assert friend_dto.tee_gender == "MALE"

    async def test_add_friend_with_tee_not_on_course_raises(
        self, qm_uow, golf_course_uow, social_uow, user_uow
    ):
        creator = await create_user(user_uow, "creator7@test.com")
        friend = await create_user(user_uow, "friend7@test.com")
        await create_accepted_friendship(social_uow, creator.id, friend.id)
        qm = await _create_pending_match(qm_uow, golf_course_uow, creator)

        # conftest's create_golf_course only has CHAMPIONSHIP/MALE and AMATEUR/MALE tees
        use_case = AddFriendToQuickMatchUseCase(qm_uow, social_uow, user_uow, golf_course_uow)
        with pytest.raises(InvalidTeeSelectionError):
            await use_case.execute(
                AddParticipantRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=creator.id.value,
                    friend_user_id=friend.id.value,
                    tee_category="AMATEUR",
                    tee_gender="FEMALE",
                )
            )
