"""Tests para SetParticipantHandicapUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import (
    SetParticipantHandicapRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.set_participant_handicap_use_case import (
    SetParticipantHandicapUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidQuickMatchStatusViolation,
    NotQuickMatchParticipantViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from tests.unit.modules.quick_match.conftest import create_user, unique_email

pytestmark = pytest.mark.asyncio


async def _create_pending_match_with_participant(qm_uow, creator_id, other_user_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    other = QuickMatchParticipant.for_user(other_user_id)
    qm.add_participant(other)
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm, other


class TestSetParticipantHandicapUseCase:
    async def test_creator_sets_override_for_registered_without_profile_handicap(
        self, qm_uow, user_uow
    ):
        creator_user = await create_user(user_uow, unique_email("creator"), handicap=10.0)
        other_user = await create_user(user_uow, unique_email("other"), handicap=None)
        qm, other = await _create_pending_match_with_participant(
            qm_uow, creator_user.id, other_user.id
        )

        use_case = SetParticipantHandicapUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            SetParticipantHandicapRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator_user.id.value,
                target_participant_id=other.participant_id.value,
                handicap=16.4,
            )
        )

        target_dto = next(
            p for p in response.participants if p.participant_id == other.participant_id.value
        )
        assert target_dto.handicap == 16.4

    async def test_override_takes_precedence_over_profile_handicap(self, qm_uow, user_uow):
        creator_user = await create_user(user_uow, unique_email("creator"), handicap=10.0)
        other_user = await create_user(user_uow, unique_email("other"), handicap=8.0)
        qm, other = await _create_pending_match_with_participant(
            qm_uow, creator_user.id, other_user.id
        )

        use_case = SetParticipantHandicapUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            SetParticipantHandicapRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator_user.id.value,
                target_participant_id=other.participant_id.value,
                handicap=20.0,
            )
        )

        target_dto = next(
            p for p in response.participants if p.participant_id == other.participant_id.value
        )
        assert target_dto.handicap == 20.0

    async def test_non_creator_cannot_edit_handicap(self, qm_uow, user_uow):
        creator_user = await create_user(user_uow, unique_email("creator"), handicap=10.0)
        other_user = await create_user(user_uow, unique_email("other"), handicap=None)
        qm, other = await _create_pending_match_with_participant(
            qm_uow, creator_user.id, other_user.id
        )

        use_case = SetParticipantHandicapUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchCreatorError):
            await use_case.execute(
                SetParticipantHandicapRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=other_user.id.value,
                    target_participant_id=other.participant_id.value,
                    handicap=16.4,
                )
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = SetParticipantHandicapUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                SetParticipantHandicapRequestDTO(
                    quick_match_id=uuid4(),
                    requester_id=uuid4(),
                    target_participant_id=uuid4(),
                    handicap=10.0,
                )
            )

    async def test_non_participant_raises(self, qm_uow, user_uow):
        creator_user = await create_user(user_uow, unique_email("creator"), handicap=10.0)
        other_user = await create_user(user_uow, unique_email("other"), handicap=None)
        qm, _other = await _create_pending_match_with_participant(
            qm_uow, creator_user.id, other_user.id
        )

        use_case = SetParticipantHandicapUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchParticipantViolation):
            await use_case.execute(
                SetParticipantHandicapRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=creator_user.id.value,
                    target_participant_id=uuid4(),
                    handicap=10.0,
                )
            )

    async def test_not_pending_raises(self, qm_uow, user_uow):
        creator_user = await create_user(user_uow, unique_email("creator"), handicap=10.0)
        other_user = await create_user(user_uow, unique_email("other"), handicap=None)
        qm, other = await _create_pending_match_with_participant(
            qm_uow, creator_user.id, other_user.id
        )
        qm.start([qm.creator_participant_id])

        use_case = SetParticipantHandicapUseCase(qm_uow, user_uow)
        with pytest.raises(InvalidQuickMatchStatusViolation):
            await use_case.execute(
                SetParticipantHandicapRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=creator_user.id.value,
                    target_participant_id=other.participant_id.value,
                    handicap=10.0,
                )
            )
