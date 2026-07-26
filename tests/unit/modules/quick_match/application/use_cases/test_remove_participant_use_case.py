"""Tests para RemoveParticipantUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import RemoveParticipantRequestDTO
from src.modules.quick_match.application.exceptions import (
    NotAuthorizedToRemoveError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.remove_participant_use_case import (
    RemoveParticipantUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


async def _create_pending_match_with_participant(qm_uow, creator_id, other_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    qm.add_participant(other_id)
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestRemoveParticipantUseCase:
    async def test_self_leave_succeeds(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        other = await create_user(user_uow, "other@test.com")
        qm = await _create_pending_match_with_participant(qm_uow, creator.id, other.id)

        use_case = RemoveParticipantUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            RemoveParticipantRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=other.id.value,
                target_user_id=other.id.value,
            )
        )

        assert len(response.participants) == 1

    async def test_creator_can_kick_participant(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        other = await create_user(user_uow, "other2@test.com")
        qm = await _create_pending_match_with_participant(qm_uow, creator.id, other.id)

        use_case = RemoveParticipantUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            RemoveParticipantRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator.id.value,
                target_user_id=other.id.value,
            )
        )

        assert len(response.participants) == 1

    async def test_third_party_cannot_remove(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        other = await create_user(user_uow, "other3@test.com")
        qm = await _create_pending_match_with_participant(qm_uow, creator.id, other.id)

        use_case = RemoveParticipantUseCase(qm_uow, user_uow)
        with pytest.raises(NotAuthorizedToRemoveError):
            await use_case.execute(
                RemoveParticipantRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=str(UserId(uuid4()).value),
                    target_user_id=other.id.value,
                )
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = RemoveParticipantUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                RemoveParticipantRequestDTO(
                    quick_match_id=uuid4(), requester_id=uuid4(), target_user_id=uuid4()
                )
            )
