"""Tests para SubmitQuickMatchHoleScoreUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import SubmitHoleScoreRequestDTO
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.submit_hole_score_use_case import (
    SubmitQuickMatchHoleScoreUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidQuickMatchStatusViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


async def _create_in_progress_match(qm_uow, creator_id, other_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    qm.add_participant(other_id)
    qm.start()
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestSubmitQuickMatchHoleScoreUseCase:
    async def test_submit_new_score_succeeds(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        other = await create_user(user_uow, "other@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        response = await use_case.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=4,
            )
        )

        assert response.score == 4

    async def test_resubmit_updates_existing_score(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        other = await create_user(user_uow, "other2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        dto = SubmitHoleScoreRequestDTO(
            quick_match_id=qm.id.value,
            player_user_id=creator.id.value,
            hole_number=1,
            score=4,
        )
        await use_case.execute(dto)
        dto2 = dto.model_copy(update={"score": 5})
        response = await use_case.execute(dto2)

        assert response.score == 5
        async with qm_uow:
            scores = await qm_uow.quick_match_hole_scores.find_by_match(qm.id)
        assert len(scores) == 1

    async def test_non_participant_cannot_submit(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        other = await create_user(user_uow, "other3@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(NotQuickMatchParticipantError):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    player_user_id=UserId(uuid4()).value,
                    hole_number=1,
                    score=4,
                )
            )

    async def test_cannot_submit_before_starting(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator4@test.com")
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        async with qm_uow:
            await qm_uow.quick_matches.add(qm)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(InvalidQuickMatchStatusViolation):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    player_user_id=creator.id.value,
                    hole_number=1,
                    score=4,
                )
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=uuid4(),
                    player_user_id=uuid4(),
                    hole_number=1,
                    score=4,
                )
            )
