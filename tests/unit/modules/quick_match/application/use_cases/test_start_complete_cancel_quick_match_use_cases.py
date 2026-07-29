"""Tests para StartQuickMatchUseCase, CompleteQuickMatchUseCase y CancelQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import StartQuickMatchRequestDTO
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.cancel_quick_match_use_case import (
    CancelQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.complete_quick_match_use_case import (
    CompleteQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.start_quick_match_use_case import (
    StartQuickMatchUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    IncompleteRosterViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


async def _create_match(qm_uow, creator_id, with_full_roster=False):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    if with_full_roster:
        qm.add_participant(QuickMatchParticipant.for_user(UserId(uuid4())))
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestStartQuickMatchUseCase:
    async def test_creator_starts_complete_roster(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        qm = await _create_match(qm_uow, creator.id, with_full_roster=True)

        use_case = StartQuickMatchUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            StartQuickMatchRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator.id.value,
                scorer_ids=[creator.id.value],
            )
        )

        assert response.status == "IN_PROGRESS"
        assert response.scorer_ids == [creator.id.value]

    async def test_incomplete_roster_raises(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        qm = await _create_match(qm_uow, creator.id, with_full_roster=False)

        use_case = StartQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(IncompleteRosterViolation):
            await use_case.execute(
                StartQuickMatchRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=creator.id.value,
                    scorer_ids=[creator.id.value],
                )
            )

    async def test_non_creator_cannot_start(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        qm = await _create_match(qm_uow, creator.id, with_full_roster=True)

        use_case = StartQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchCreatorError):
            await use_case.execute(
                StartQuickMatchRequestDTO(
                    quick_match_id=qm.id.value, requester_id=uuid4(), scorer_ids=[uuid4()]
                )
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = StartQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                StartQuickMatchRequestDTO(
                    quick_match_id=uuid4(), requester_id=uuid4(), scorer_ids=[uuid4()]
                )
            )


class TestCompleteQuickMatchUseCase:
    async def test_creator_completes_in_progress_match(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator4@test.com")
        qm = await _create_match(qm_uow, creator.id, with_full_roster=True)
        qm.start([qm.creator_participant_id])
        async with qm_uow:
            await qm_uow.quick_matches.update(qm)

        use_case = CompleteQuickMatchUseCase(qm_uow, user_uow)
        response = await use_case.execute(str(qm.id.value), str(creator.id.value))

        assert response.status == "COMPLETED"


class TestCancelQuickMatchUseCase:
    async def test_creator_cancels_pending_match(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator5@test.com")
        qm = await _create_match(qm_uow, creator.id)

        use_case = CancelQuickMatchUseCase(qm_uow, user_uow)
        response = await use_case.execute(str(qm.id.value), str(creator.id.value))

        assert response.status == "CANCELLED"
