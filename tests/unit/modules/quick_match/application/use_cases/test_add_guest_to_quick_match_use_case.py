"""Tests para AddGuestToQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import (
    AddGuestParticipantRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.add_guest_to_quick_match_use_case import (
    AddGuestToQuickMatchUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


async def _create_pending_match(qm_uow, creator_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestAddGuestToQuickMatchUseCase:
    async def test_creator_adds_guest_succeeds(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        qm = await _create_pending_match(qm_uow, creator.id)

        use_case = AddGuestToQuickMatchUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            AddGuestParticipantRequestDTO(
                quick_match_id=qm.id.value,
                requester_id=creator.id.value,
                first_name="Jane",
                last_name="Doe",
                handicap=18.4,
            )
        )

        assert len(response.participants) == 2
        guest_dto = next(p for p in response.participants if p.is_guest)
        assert guest_dto.name == "Jane Doe"
        assert guest_dto.handicap == 18.4
        assert guest_dto.user_id is None

    async def test_non_creator_cannot_add_guest(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        qm = await _create_pending_match(qm_uow, creator.id)

        use_case = AddGuestToQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchCreatorError):
            await use_case.execute(
                AddGuestParticipantRequestDTO(
                    quick_match_id=qm.id.value,
                    requester_id=uuid4(),
                    first_name="Jane",
                    last_name="Doe",
                )
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = AddGuestToQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                AddGuestParticipantRequestDTO(
                    quick_match_id=uuid4(),
                    requester_id=uuid4(),
                    first_name="Jane",
                    last_name="Doe",
                )
            )
