"""Tests para ListMyQuickMatchesUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.use_cases.list_my_quick_matches_use_case import (
    ListMyQuickMatchesUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


class TestListMyQuickMatchesUseCase:
    async def test_lists_only_matches_where_user_participates(self, qm_uow, user_uow):
        me = await create_user(user_uow, "me@test.com")
        other = await create_user(user_uow, "other@test.com")

        mine = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=me.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        not_mine = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=other.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        async with qm_uow:
            await qm_uow.quick_matches.add(mine)
            await qm_uow.quick_matches.add(not_mine)

        use_case = ListMyQuickMatchesUseCase(qm_uow, user_uow)
        result = await use_case.execute(str(me.id.value))

        assert result.total_count == 1
        assert result.quick_matches[0].id == mine.id.value
