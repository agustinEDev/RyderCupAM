"""Tests para HideQuickMatchUseCase y UnhideQuickMatchUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import HideQuickMatchRequestDTO
from src.modules.quick_match.application.exceptions import QuickMatchNotFoundError
from src.modules.quick_match.application.use_cases.hide_quick_match_use_case import (
    HideQuickMatchUseCase,
)
from src.modules.quick_match.application.use_cases.unhide_quick_match_use_case import (
    UnhideQuickMatchUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def _create_pending_match_with_participant(qm_uow, creator_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    other = QuickMatchParticipant.for_user(UserId(uuid4()))
    qm.add_participant(other)
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm, other


class TestHideQuickMatchUseCase:
    async def test_creator_can_hide(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, _other = await _create_pending_match_with_participant(qm_uow, creator)

        use_case = HideQuickMatchUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert stored.is_hidden_for(qm.creator_participant_id)

    async def test_non_creator_participant_can_hide(self, qm_uow, user_uow):
        """Cualquier participante puede ocultarla, no solo el creador."""
        creator = UserId(uuid4())
        qm, other = await _create_pending_match_with_participant(qm_uow, creator)

        use_case = HideQuickMatchUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(
                quick_match_id=qm.id.value, requester_id=other.user_id.value
            )
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert stored.is_hidden_for(other.participant_id)
        assert not stored.is_hidden_for(qm.creator_participant_id)

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = HideQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                HideQuickMatchRequestDTO(quick_match_id=uuid4(), requester_id=uuid4())
            )


class TestUnhideQuickMatchUseCase:
    async def test_reverses_a_previous_hide(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, _other = await _create_pending_match_with_participant(qm_uow, creator)
        qm.hide_for(qm.creator_participant_id)
        async with qm_uow:
            await qm_uow.quick_matches.update(qm)

        use_case = UnhideQuickMatchUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert not stored.is_hidden_for(qm.creator_participant_id)

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = UnhideQuickMatchUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                HideQuickMatchRequestDTO(quick_match_id=uuid4(), requester_id=uuid4())
            )
