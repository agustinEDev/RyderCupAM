"""Tests para GetQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import SubmitHoleScoreRequestDTO
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.get_quick_match_use_case import (
    GetQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.submit_hole_score_use_case import (
    SubmitQuickMatchHoleScoreUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
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


class TestGetQuickMatchUseCase:
    async def test_participant_can_view_detail(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        other = await create_user(user_uow, "other@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = GetQuickMatchUseCase(qm_uow, user_uow)
        detail = await use_case.execute(str(qm.id.value), str(creator.id.value))

        assert detail.status == "IN_PROGRESS"
        assert detail.hole_scores == []
        assert detail.standing is None

    async def test_non_participant_cannot_view(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        other = await create_user(user_uow, "other2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = GetQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchParticipantError):
            await use_case.execute(str(qm.id.value), str(UserId(uuid4()).value))

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = GetQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(str(uuid4()), str(uuid4()))

    async def test_standing_computed_after_complete_hole(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        other = await create_user(user_uow, "other3@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        submit_uc = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=4,
            )
        )
        await submit_uc.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=other.id.value,
                hole_number=1,
                score=5,
            )
        )

        get_uc = GetQuickMatchUseCase(qm_uow, user_uow)
        detail = await get_uc.execute(str(qm.id.value), str(creator.id.value))

        assert detail.standing is not None
        assert detail.standing.holes_played == 1
        assert detail.standing.leading_team == "A"
        assert detail.standing.status == "1UP"
